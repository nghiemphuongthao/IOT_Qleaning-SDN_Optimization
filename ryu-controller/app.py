from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from webob import Response
from ryu.app.wsgi import WSGIApplication, ControllerBase, route
import json

class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = {}
        
        # Setup WSGI for REST API
        wsgi = kwargs['wsgi']
        self.wsgi = wsgi
        wsgi.register(StatsController, {'app': self})

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info(f"Switch connected: dpid={datapath.id}")
        self.switches[datapath.id] = datapath

        # Install default flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes", 
                              ev.msg.msg_len, ev.msg.total_len)
            
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("Packet in - DPID: %s, SRC: %s, DST: %s, IN_PORT: %s", 
                         dpid, src, dst, in_port)

        # Learn MAC address
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow entry if not flooding
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)

        # Send packet out
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def get_flow_stats(self):
        """Get MAC learning table"""
        return self.mac_to_port

    def get_switches(self):
        """Get connected switches"""
        return list(self.switches.keys())

class StatsController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(StatsController, self).__init__(req, link, data, **config)
        self.app = data['app']

    @route('stats', '/stats/flow/{dpid}', methods=['GET'])
    def get_flow_stats(self, req, dpid, **kwargs):
        """Get flow statistics for specific switch"""
        try:
            stats = self.app.get_flow_stats()
            dpid_int = int(dpid)
            
            if dpid_int in stats:
                body = json.dumps({
                    'dpid': dpid_int,
                    'mac_to_port': stats[dpid_int]
                })
                return Response(content_type='application/json', body=body)
            else:
                return Response(
                    status=404, 
                    body=json.dumps({'error': f'Switch {dpid} not found'})
                )
        except ValueError:
            return Response(
                status=400, 
                body=json.dumps({'error': 'Invalid DPID format'})
            )
        except Exception as e:
            return Response(
                status=500, 
                body=json.dumps({'error': str(e)})
            )

    @route('portstats', '/stats/port/{dpid}', methods=['GET'])
    def get_port_stats(self, req, dpid, **kwargs):
        """Get port statistics for specific switch"""
        try:
            # In a real implementation, you would query the switch here
            # This is dummy data for demonstration
            dummy_data = {
                'dpid': int(dpid),
                'ports': {
                    1: {'packets_rx': 100, 'bytes_rx': 10240, 'packets_tx': 95, 'bytes_tx': 9728},
                    2: {'packets_rx': 150, 'bytes_rx': 15360, 'packets_tx': 145, 'bytes_tx': 14848},
                    3: {'packets_rx': 80, 'bytes_rx': 8192, 'packets_tx': 78, 'bytes_tx': 7987}
                }
            }
            body = json.dumps(dummy_data)
            return Response(content_type='application/json; charset=utf-8', body=body)
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))

    @route('switches', '/stats/switches', methods=['GET'])
    def get_switches(self, req, **kwargs):
        """Get list of connected switches"""
        try:
            switches = self.app.get_switches()
            body = json.dumps({'switches': switches})
            return Response(content_type='application/json', body=body)
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))