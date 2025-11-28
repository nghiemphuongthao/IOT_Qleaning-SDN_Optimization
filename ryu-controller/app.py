from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp
from ryu.lib import hub
import json, time, os, threading
from flask import Flask, jsonify

# -------------------------------
# Tích hợp Flask API
# -------------------------------
app = Flask(__name__)

class QLearningSDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(QLearningSDNController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.flow_stats = {}
        self.port_stats = {}
        self.metrics_history = []
        self.logger.info("QLearningSDNController initialized")

        # Thread giám sát mạng
        self.monitor_thread = hub.spawn(self._monitor_network)

        # Khởi chạy Flask REST API server trong thread riêng
        threading.Thread(target=self._start_rest_api, daemon=True).start()

    # -------------------------------
    # REST API cho Q-learning agent
    # -------------------------------
    def _start_rest_api(self):
        @app.route('/state', methods=['GET'])
        def get_state():
            state = self.get_network_state()
            return jsonify(state)
        
        @app.route('/flows', methods=['GET'])
        def get_flows():
            return jsonify(self.flow_stats)
        
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

    # -------------------------------
    # Các hàm xử lý Ryu gốc 
    # -------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)
        self.datapaths[datapath.id] = datapath
        self.logger.info(f"Switch {datapath.id} connected")

    def _add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match.get('in_port', None)
        if in_port is None:
            return
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth:
            return
        self.mac_to_port.setdefault(datapath.id, {})
        self.mac_to_port[datapath.id][eth.src] = in_port
        if eth.ethertype == 0x0806:
            self._handle_arp(datapath, in_port, eth, pkt, msg.data)
        elif eth.ethertype == 0x0800:
            self._handle_ip_packet(datapath, in_port, eth, pkt, msg.data)

    def _handle_arp(self, datapath, in_port, eth, pkt, data):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _handle_ip_packet(self, datapath, in_port, eth, pkt, data):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            return
        src_ip, dst_ip = ip_pkt.src, ip_pkt.dst
        dpid = datapath.id
        out_port = self._get_optimal_path(dpid, src_ip, dst_ip, in_port)
        if out_port is None:
            return
        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_src=eth.src, eth_dst=eth.dst,
                                eth_type=eth.ethertype, ipv4_src=src_ip, ipv4_dst=dst_ip)
        self._add_flow(datapath, 1, match, actions)
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _get_optimal_path(self, switch_id, src_ip, dst_ip, in_port):
        if switch_id == 1:
            if dst_ip.startswith('10.0.2.'): return 2
            elif dst_ip.startswith('10.0.3.'): return 3
            elif dst_ip.startswith('10.0.4.'): return 4
            elif dst_ip.startswith('10.0.5.'): return 5
        return datapath.ofproto.OFPP_FLOOD

    def _monitor_network(self):
        while True:
            try:
                for dp in list(self.datapaths.values()):
                    self._request_stats(dp)
                self._save_metrics()
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
            hub.sleep(10)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY))
        datapath.send_msg(parser.OFPFlowStatsRequest(datapath))

    def _save_metrics(self):
        os.makedirs("results", exist_ok=True)
        metrics = {
            'switches': len(self.datapaths),
            'mac_entries': sum(len(t) for t in self.mac_to_port.values()),
            'timestamp': time.time()
        }
        with open("results/controller_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

    def get_network_state(self):
        return {
            'switch_count': len(self.datapaths),
            'mac_entries': sum(len(t) for t in self.mac_to_port.values()),
            'timestamp': time.time()
        }
