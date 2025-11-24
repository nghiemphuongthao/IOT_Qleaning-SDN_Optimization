#!/usr/bin/env python3
"""
SDN Controller với Q-learning Integration - Ryu Controller
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp
from ryu.lib import hub
import json
import time
import os

class QLearningSDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(QLearningSDNController, self).__init__(*args, **kwargs)
        
        # Network state tracking
        self.mac_to_port = {}
        self.datapaths = {}
        self.flow_stats = {}
        self.port_stats = {}
        
        # Q-learning integration
        self.qlearning_enabled = True
        self.metrics_history = []
        
        # Khởi chạy monitoring thread
        self.monitor_thread = hub.spawn(self._monitor_network)
        
        self.logger.info("🎮 QLearningSDNController initialized")
    
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Xử lý khi switch kết nối tới controller"""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                        ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)
        
        self.datapaths[datapath.id] = datapath
        self.logger.info(f"🔌 Switch {datapath.id} connected")
    
    def _add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """Thêm flow entry vào switch"""
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
        """Xử lý packet-in messages từ switches"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        
        if not eth:
            return
            
        # Learn MAC address
        self.mac_to_port.setdefault(datapath.id, {})
        self.mac_to_port[datapath.id][eth.src] = in_port
        
        self.logger.debug(f"📦 PacketIn: src={eth.src}, dst={eth.dst}, in_port={in_port}")
        
        # Handle ARP packets
        if eth.ethertype == 0x0806:
            self._handle_arp(datapath, in_port, eth, pkt, msg.data)
            return
            
        # Handle IP packets với Q-learning routing
        if eth.ethertype == 0x0800:
            self._handle_ip_packet(datapath, in_port, eth, pkt, msg.data)
    
    def _handle_arp(self, datapath, in_port, eth, pkt, data):
        """Xử lý ARP packets"""
        arp_pkt = pkt.get_protocol(arp.arp)
        if not arp_pkt:
            return
            
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Flood ARP packets để học MAC addresses
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
        
        self.logger.debug(f"🔄 ARP handling: {arp_pkt.src_ip} -> {arp_pkt.dst_ip}")
    
    def _handle_ip_packet(self, datapath, in_port, eth, pkt, data):
        """Xử lý IP packets với intelligent routing"""
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            return
            
        dst_ip = ip_pkt.dst
        src_ip = ip_pkt.src
        dpid = datapath.id
        
        self.logger.info(f"🌐 IP Packet: {src_ip} -> {dst_ip} on switch s{dpid}")
        
        # Sử dụng Q-learning để chọn optimal path
        out_port = self._get_optimal_path(dpid, src_ip, dst_ip, in_port)
        
        if out_port is None:
            self.logger.warning(f"❌ No path found for {src_ip} -> {dst_ip}")
            return
            
        # Install flow entry và forward packet
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
        
        # Add flow entry để xử lý các packet tiếp theo
        self._add_flow(datapath, 1, match, actions)
        
        # Forward packet hiện tại
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port, 
            actions=actions, 
            data=data
        )
        datapath.send_msg(out)
        
        self.logger.info(f"✅ Installed flow: {src_ip} -> {dst_ip} via port {out_port} on s{dpid}")
    
    def _get_optimal_path(self, switch_id, src_ip, dst_ip, in_port):
        """Sử dụng Q-learning để chọn optimal path"""
        # Simple routing logic - sẽ được tích hợp với Q-learning agent
        if switch_id == 1:  # Core switch s1
            if dst_ip.startswith('10.0.2.'): return 2
            elif dst_ip.startswith('10.0.3.'): return 3
            elif dst_ip.startswith('10.0.4.'): return 4
            elif dst_ip.startswith('10.0.5.'): return 5
            elif dst_ip.startswith('10.0.1.'): 
                # Routing to servers/gateway
                if dst_ip == '10.0.1.10': return 1
                elif dst_ip == '10.0.1.11': return 1
                elif dst_ip == '10.0.1.1': return 1
        else:
            # Edge switches - forward to core (port 1) hoặc local devices
            if dst_ip.startswith('10.0.1.'): return 1  # To core
            else: return 2  # Local device (simplified)
            
        return 1  # Default
    
    def _monitor_network(self):
        """Thread thu thập network metrics"""
        while True:
            try:
                for datapath in self.datapaths.values():
                    self._request_stats(datapath)
                
                # Lưu metrics định kỳ
                self._save_metrics()
                
                hub.sleep(10)  # Thu thập mỗi 10 giây
                
            except Exception as e:
                self.logger.error(f"❌ Monitoring error: {e}")
                hub.sleep(5)
    
    def _request_stats(self, datapath):
        """Request statistics từ switch"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        try:
            # Request port statistics
            req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
            datapath.send_msg(req)
            
            # Request flow statistics  
            req = parser.OFPFlowStatsRequest(datapath)
            datapath.send_msg(req)
            
        except Exception as e:
            self.logger.error(f"❌ Error requesting stats: {e}")
    
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """Xử lý port statistics reply"""
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        self.port_stats[dpid] = {}
        
        for stat in body:
            port_no = stat.port_no
            if port_no not in self.port_stats[dpid]:
                self.port_stats[dpid][port_no] = []
                
            port_stat = {
                'rx_packets': stat.rx_packets,
                'tx_packets': stat.tx_packets,
                'rx_bytes': stat.rx_bytes,
                'tx_bytes': stat.tx_bytes,
                'rx_errors': stat.rx_errors,
                'tx_errors': stat.tx_errors,
                'timestamp': time.time()
            }
            
            self.port_stats[dpid][port_no].append(port_stat)
            
            # Giữ lịch sử 100 samples
            if len(self.port_stats[dpid][port_no]) > 100:
                self.port_stats[dpid][port_no].pop(0)
    
    def _save_metrics(self):
        """Lưu network metrics"""
        try:
            metrics = {
                'timestamp': time.time(),
                'active_switches': len(self.datapaths),
                'total_flows': sum(len(stats) for stats in self.flow_stats.values()),
                'port_stats': self.port_stats,
                'mac_table_size': sum(len(table) for table in self.mac_to_port.values())
            }
            
            self.metrics_history.append(metrics)
            
            # Lưu ra file
            os.makedirs('results', exist_ok=True)
            with open('results/controller_metrics.json', 'w') as f:
                json.dump(self.metrics_history, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"❌ Error saving metrics: {e}")
    
    def get_network_state(self):
        """Trả về network state cho Q-learning agent"""
        return {
            'switch_count': len(self.datapaths),
            'active_flows': sum(len(stats) for stats in self.flow_stats.values()),
            'mac_entries': sum(len(table) for table in self.mac_to_port.values()),
            'timestamp': time.time()
        }