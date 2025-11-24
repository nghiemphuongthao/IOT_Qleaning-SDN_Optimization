from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4
from ryu.lib import hub
import json
import os

class QLearningRyuController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(QLearningRyuController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.metrics = {
            'throughput': 0,
            'latency': 0,
            'packet_loss': 0,
            'active_flows': 0
        }
        
        self.monitor_thread = hub.spawn(self._monitor_network)
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                        ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        
        self.datapaths[datapath.id] = datapath
        self.logger.info(f"Switch {datapath.id} connected")
    
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
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        
        if not eth:
            return
            
        if eth.ethertype == 0x0806:  # ARP
            self.handle_arp(datapath, in_port, eth, msg.data)
            return
            
        self.handle_ip_packet(datapath, in_port, eth, pkt, msg.data)
    
    def handle_arp(self, datapath, in_port, eth, data):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
    
    def handle_ip_packet(self, datapath, in_port, eth, pkt, data):
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            return
            
        dst_ip = ip_pkt.dst
        src_ip = ip_pkt.src
        
        out_port = self.get_optimal_path(datapath.id, src_ip, dst_ip, in_port)
        
        if out_port is None:
            self.logger.warning(f"No path found for {src_ip} -> {dst_ip}")
            return
            
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(
            in_port=in_port,
            eth_src=eth.src, 
            eth_dst=eth.dst,
            eth_type=eth.ethertype,
            ipv4_src=src_ip, 
            ipv4_dst=dst_ip
        )
        
        if hasattr(msg, 'buffer_id') and msg.buffer_id != ofproto.OFP_NO_BUFFER:
            self.add_flow(datapath, 1, match, actions, msg.buffer_id)
        else:
            self.add_flow(datapath, 1, match, actions)
            
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port, 
            actions=actions, 
            data=data
        )
        datapath.send_msg(out)
        
        self.logger.info(f"Installed flow: {src_ip} -> {dst_ip} via port {out_port}")
    
    def get_optimal_path(self, switch_id, src_ip, dst_ip, in_port):
        # Simple routing based on IP subnets
        if switch_id == 1:  # s1
            if dst_ip.startswith('10.0.2.'): return 2
            elif dst_ip.startswith('10.0.3.'): return 3
            elif dst_ip.startswith('10.0.4.'): return 4
            elif dst_ip.startswith('10.0.5.'): return 5
        else:
            return 1  # Default to port 1
            
        return 1
    
    def _monitor_network(self):
        while True:
            for datapath in self.datapaths.values():
                self._request_stats(datapath)
            hub.sleep(10)
    
    def _request_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        try:
            req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
            datapath.send_msg(req)
            
            req = parser.OFPFlowStatsRequest(datapath)
            datapath.send_msg(req)
        except Exception as e:
            self.logger.error(f"Error requesting stats: {e}")