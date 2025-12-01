# ryu_app.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.topology import event
from ryu.topology.api import get_switch, get_link
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub
import networkx as nx
import zmq, json, time, os

ZMQ_PUB_PORT = int(os.environ.get('ZMQ_PUB_PORT', 5556))
ZMQ_REP_PORT = int(os.environ.get('ZMQ_REP_PORT', 5557))

class RyuZMQ(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RyuZMQ, self).__init__(*args, **kwargs)
        self.net = nx.DiGraph()
        self.mac_table = {}
        self.port_stats = {}    # {dpid: {port_no: tx_bytes}}
        self.port_speed = {}    # {dpid: {port_no: bytes_delta}}
        # ZeroMQ
        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.PUB)
        self.pub.bind(f"tcp://0.0.0.0:{ZMQ_PUB_PORT}")
        self.rep = self.context.socket(zmq.REP)
        self.rep.bind(f"tcp://0.0.0.0:{ZMQ_REP_PORT}")
        # launch threads
        hub.spawn(self._rep_loop)
        hub.spawn(self._state_publisher)
        hub.spawn(self._monitor_stats)

    # Topology discovery
    @set_ev_cls(event.EventSwitchEnter)
    def on_switch_enter(self, ev):
        switches = get_switch(self, None)
        links = get_link(self, None)
        self.net.clear()
        for s in switches:
            self.net.add_node(s.dp.id)
        for l in links:
            s1, p1 = l.src.dpid, l.src.port_no
            s2, p2 = l.dst.dpid, l.dst.port_no
            self.net.add_edge(s1, s2, port=p1, load=0)
            self.net.add_edge(s2, s1, port=p2, load=0)
        self.logger.info(f"Topology nodes: {self.net.nodes()} edges: {self.net.edges(data=True)}")

    # default table-miss
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=0, match=match, instructions=inst))

    # packet in: simple learning + path calc
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        in_port = msg.match.get('in_port', None)
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth:
            return
        if eth.ethertype == 0x88cc:
            return
        src = eth.src; dst = eth.dst
        self.mac_table.setdefault(dpid, {})
        self.mac_table[dpid][src] = in_port

        # find dst location
        dst_sw = None
        for sw in self.mac_table:
            if dst in self.mac_table[sw]:
                dst_sw = sw
                break

        if dst_sw is None:
            out_port = ofp.OFPP_FLOOD
        else:
            if dpid == dst_sw:
                out_port = self.mac_table[dpid][dst]
            else:
                try:
                    path = nx.shortest_path(self.net, dpid, dst_sw, weight='load')
                    next_hop = path[1]
                    out_port = self.net[dpid][next_hop]['port']
                except Exception:
                    out_port = ofp.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
        dp.send_msg(parser.OFPFlowMod(datapath=dp, match=match, priority=1,
                                     instructions=[parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]))
        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        dp.send_msg(parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                       in_port=in_port, actions=actions, data=data))

    # request port stats
    def _monitor_stats(self):
        while True:
            for s in list(self.net.nodes()):
                # get datapath object
                # using get_switch to get the DP objects might be needed; simpler: send request to known datapaths
                pass
            # hub.sleep small; actual port stats handled by OFPPortStatsReply handler when replies come
            hub.sleep(1.0)

    # handle port stats replies (useful if port stats have been requested)
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_handler(self, ev):
        dp = ev.msg.datapath
        dpid = dp.id
        body = ev.msg.body
        if dpid not in self.port_stats:
            self.port_stats[dpid] = {}
            self.port_speed[dpid] = {}
        for stat in body:
            port_no = stat.port_no
            tx = stat.tx_bytes
            prev = self.port_stats[dpid].get(port_no, tx)
            speed = max(tx - prev, 0)
            self.port_stats[dpid][port_no] = tx
            self.port_speed[dpid][port_no] = speed
        # update net loads (match by port)
        for u, v, data in self.net.edges(data=True):
            port = data.get('port')
            if port is not None:
                data['load'] = self.port_speed.get(u, {}).get(port, 0)

    # ZeroMQ REP loop: receive actions
    def _rep_loop(self):
        while True:
            try:
                msg = self.rep.recv_json()
                # Expect action: {"type":"action","flow": {...}}
                if msg.get('type') == 'action':
                    flow = msg.get('flow', {})
                    ok, info = self._install_flow_from_action(flow)
                    if ok:
                        self.rep.send_json({"status":"ok", "msg": info})
                    else:
                        self.rep.send_json({"status":"error", "msg": info})
                else:
                    self.rep.send_json({"status":"error", "msg":"unknown message type"})
            except Exception as e:
                try:
                    self.rep.send_json({"status":"error", "msg": str(e)})
                except:
                    pass

    # apply flow described as path or as (dpid,out_port)
    def _install_flow_from_action(self, flow):
        try:
            path = flow.get('path')  # list of dpids
            priority = int(flow.get('priority', 10))
            timeout = int(flow.get('timeout', 60))
            src_ip = flow.get('src_ip')
            dst_ip = flow.get('dst_ip')
            if not path or len(path) < 2:
                return False, "invalid path"
            # install flows along path
            for i in range(len(path)-1):
                u = path[i]; v = path[i+1]
                port = self.net[u][v]['port']
                dp = None
                # find datapath with id==u
                for sw in get_switch(self, None):
                    if sw.dp.id == u:
                        dp = sw.dp; break
                if dp is None:
                    continue
                parser = dp.ofproto_parser
                ofp = dp.ofproto
                match = parser.OFPMatch(eth_type=0x0800, ipv4_src=src_ip, ipv4_dst=dst_ip)
                actions = [parser.OFPActionOutput(int(port))]
                dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority,
                                             match=match, instructions=[parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)],
                                             hard_timeout=timeout))
            return True, "flows installed"
        except Exception as e:
            return False, str(e)

    # state publisher: publish simple state periodically
    def _state_publisher(self):
        while True:
            try:
                state = {
                    "type": "state",
                    "timestamp": time.time(),
                    "switches": list(self.net.nodes()),
                    "links": []
                }
                for u, v, data in self.net.edges(data=True):
                    state["links"].append({
                        "u": u, "v": v, "port_u": data.get('port'), "load": data.get('load', 0)
                    })
                state["mac_table"] = self.mac_table
                self.pub.send_json(state)
            except Exception as e:
                self.logger.error(f"Publish error: {e}")
            hub.sleep(1.0)
