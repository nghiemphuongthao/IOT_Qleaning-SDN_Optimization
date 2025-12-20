import json
import time
import pprint
from operator import attrgetter
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, ether_types
from ryu.lib import hub
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
import numpy as np
import random
import csv
import os

from q_agent import QAgent
from model import QoSModel

# --- CONFIGURATION ---
CONGESTION_THRESHOLD = 200000 
MONITOR_INTERVAL = 2            # Monitor every 2 seconds

SW256_DPID = 256
CLOUD_PORT_MAIN = 1
CLOUD_PORT_BACKUP = 5

ACTION_MAP = {
    0: (CLOUD_PORT_MAIN, 0, 0xffff),
    1: (CLOUD_PORT_MAIN, 1, 700),
    2: (CLOUD_PORT_MAIN, 2, 500),
    3: (CLOUD_PORT_BACKUP, 0, 0xffff),
}

simple_switch_instance_name = 'simple_switch_api_app'
url = '/router/{dpid}'

# ANSI color codes for pretty logging
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class AntiLoopController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(AntiLoopController, self).__init__(*args, **kwargs)
        self.logger.info(f"{Colors.GREEN}--> [SYSTEM] Controller V2 Debug Ready.{Colors.RESET}")
        
        wsgi = kwargs['wsgi']
        wsgi.register(RestRouterController, {simple_switch_instance_name: self})

        self.GATEWAY_MAC = "00:00:00:00:01:00"
        self.CLOUD_MAC   = "00:00:00:00:00:FF" 
        
        self.datapaths = {}
        self.groups_installed = {} 
        self.prev_stats = {} 
        self.prev_queue_stats = {}
        self.q_port_load = {}      # Lưu tốc độ port/queue cho Q-Learning
        self.q_drops = {}          # Lưu drops cho Q-Learning

        # Biến Q-Learning
        self.model = QoSModel(congestion_threshold=CONGESTION_THRESHOLD)

        self.q_agent = QAgent(n_states=3, n_actions=4)

        self.q_last_state = None
        self.q_last_action = None
        self.q_last_port = None
        self.q_last_qid = None

        self.static_arp_table = {
            "10.0.100.2": self.CLOUD_MAC,
            "10.0.200.2": self.CLOUD_MAC,
            "10.0.1.1": "00:00:00:00:00:01", "10.0.1.2": "00:00:00:00:00:02",
            "10.0.1.3": "00:00:00:00:00:03", "10.0.2.4": "00:00:00:00:00:04",
            "10.0.2.5": "00:00:00:00:00:05", "10.0.3.6": "00:00:00:00:00:06",
            "10.0.3.7": "00:00:00:00:00:07", "10.0.4.8": "00:00:00:00:00:08",
            "10.0.4.9": "00:00:00:00:00:09", "10.0.4.10": "00:00:00:00:00:0a",
        }

        # --- DEFAULT ROUTING TABLE ---
        self.routing_table = {
            # G1 (Switch 256)
            256: { 
                "10.0.100": 1, "10.0.200": 1, 
                "10.0.1": 2, "10.0.2": 3, "10.0.3": 4, "10.0.4": 5
            },
            # G2 (Switch 512)
            512: { "10.0.3": 2, "default": 1 },
            # G3 (Switch 768)
            768: { 
                "10.0.4": 2,
                "10.0.100": 1, # Default via G1
                "10.0.200": 3, # Direct
                "default": 1 
            }
        }
        self.print_routing_table_pretty()

        self.monitor_thread = hub.spawn(self._monitor)

    # --- FEATURE 1: PRETTY PRINT ROUTING TABLE ---
    def print_routing_table_pretty(self):
        print(f"\n{Colors.BLUE}{'='*60}")
        print(f"{'CURRENT ROUTING TABLE (Static)':^60}")
        print(f"{'='*60}{Colors.RESET}")
        print(f"{'Switch ID':<15} | {'Dest Subnet/IP':<15} | {'Output Port':<10}")
        print("-" * 46)
        
        for dpid, routes in self.routing_table.items():
            first = True
            for dest, port in routes.items():
                sw_name = f"SW-{dpid}" if first else ""
                print(f"{sw_name:<15} | {dest:<15} | {port:<10}")
                first = False
            print("-" * 46)
        print("\n")

    # --- FEATURE 2: MONITOR & CONGESTION WARNING + Q-LEARNING ---
    def _monitor(self):
        while True:
            try:    
                for dp in list(self.datapaths.values()):
                    if dp.id in [256, 768]:
                        self._request_stats(dp)
                hub.sleep(0.3)
                self.run_qlearning_control()
            except Exception: 
                self.logger.exception("[MONITOR] recover")
            hub.sleep(MONITOR_INTERVAL)


    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
        datapath.send_msg(req)
        req = parser.OFPQueueStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY, datapath.ofproto.OFPQ_ALL)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        for stat in body:
            port_no = stat.port_no
            if port_no > 100: continue 
            
            key = (dpid, port_no)
            rx_bytes = stat.rx_bytes
            tx_bytes = stat.tx_bytes
            
            if key in self.prev_stats:
                prev_rx, prev_tx, prev_time = self.prev_stats[key]
                duration = time.time() - prev_time
                if duration > 0:
                    speed_tx = (tx_bytes - prev_tx) / duration
                    speed_rx = (rx_bytes - prev_rx) / duration
                    total_speed = speed_tx + speed_rx
                    
                    self.q_port_load[key] = total_speed
                    
                    # RED ALERT LOGIC
                    if speed_tx > CONGESTION_THRESHOLD or speed_rx > CONGESTION_THRESHOLD:
                        max_speed = max(speed_tx, speed_rx) / 1000000
                        print(f"{Colors.RED}[!] CONGESTION ALERT: Switch {dpid} Port {port_no} | Load: {max_speed:.2f} MB/s{Colors.RESET}")
            
            self.prev_stats[key] = (rx_bytes, tx_bytes, time.time())

    @set_ev_cls(ofp_event.EventOFPQueueStatsReply, MAIN_DISPATCHER)
    def _queue_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        for stat in sorted(body, key=attrgetter('port_no', 'queue_id')):
            port_no = stat.port_no
            if port_no > 100: continue
            queue_id = stat.queue_id
            tx_bytes = stat.tx_bytes
            tx_errors = stat.tx_errors
            
            key = (dpid, port_no, queue_id)
            if key in self.prev_queue_stats:
                prev_tx_bytes, prev_tx_errors, prev_time = self.prev_queue_stats[key]
                duration = time.time() - prev_time
                if duration > 1:
                    speed = (tx_bytes - prev_tx_bytes) / duration
                    drops = tx_errors - prev_tx_errors
                    
                    self.q_port_load[key] = speed
                    self.q_drops[key] = drops
                    
                    if drops > 0:
                        print(f"{Colors.RED}[DROP] SW{dpid} P{port_no} Q{queue_id}: {drops} drops{Colors.RESET}")
            
            self.prev_queue_stats[key] = (tx_bytes, tx_errors, time.time())

    # ================= CƠ CHẾ QUEUE OPTIMIZATION CHO CLOUD TRAFFIC =================
    def _setup_queues(self, dp):
        parser = dp.ofproto_parser

        try:
        # Queues cho Port Main (1)
            rates = [0xffff, 700, 500, 300]  # unlimited, 70%, 50%, 30%
            queues_main = []
            for qid, rate in enumerate(rates):
            # Một số bản Ryu không có OFPQueuePropMaxRate -> fallback MinRate
                if hasattr(parser, "OFPQueuePropMaxRate"):
                    props = [parser.OFPQueuePropMaxRate(rate)]
                else:
                    props = [parser.OFPQueuePropMinRate(rate)]
            # ✅ dùng positional args để tránh lỗi keyword
                queues_main.append(parser.OFPPacketQueue(qid, props, 0))

        # Nếu parser không có OFPQueueMod thì bỏ qua (OVS thường cấu hình queue qua ovs-vsctl)
            if not hasattr(parser, "OFPQueueMod"):
                self.logger.warning("[QUEUE] OFPQueueMod not supported by this Ryu/OVS. Skip queue install (configure via ovs-vsctl in Mininet).")
                return

            dp.send_msg(parser.OFPQueueMod(dp, CLOUD_PORT_MAIN, queues_main))

        # Queue cho Port Backup (5) - chỉ 1 queue unlimited
            if hasattr(parser, "OFPQueuePropMaxRate"):
                props_b = [parser.OFPQueuePropMaxRate(0xffff)]
            else:
                props_b = [parser.OFPQueuePropMinRate(0xffff)]
            queues_backup = [parser.OFPPacketQueue(0, props_b, 0)]

            dp.send_msg(parser.OFPQueueMod(dp, CLOUD_PORT_BACKUP, queues_backup))

            self.logger.info(f"{Colors.GREEN}[QUEUE] Queues installed on SW{dp.id} Ports {CLOUD_PORT_MAIN} & {CLOUD_PORT_BACKUP}.{Colors.RESET}")

        except Exception:
        # ✅ không làm chết app nếu queue setup lỗi
            self.logger.exception("[QUEUE] setup failed; continue without queue config")

    def _update_cloud_flow(self, dp, out_port, qid):
            parser = dp.ofproto_parser
            ofp = dp.ofproto
        
        # Xóa flow cũ (priority 50)
            for subnet in ["10.0.100.0/24", "10.0.200.0/24"]:
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=subnet)
                mod = parser.OFPFlowMod(
                    datapath=dp, 
                    command=ofp.OFPFC_DELETE, 
                    out_port=ofp.OFPP_ANY, 
                    out_group=ofp.OFPG_ANY, 
                    priority=50, 
                    match=match
                )
                dp.send_msg(mod)
        
        # Cài flow mới
            for subnet in ["10.0.100.0/24", "10.0.200.0/24"]:
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=subnet)
                actions = [
                    parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                    parser.OFPActionSetField(eth_dst=self.CLOUD_MAC),
                ]
                if qid is not None:
                    actions.append(parser.OFPActionSetQueue(qid))
                actions.append(parser.OFPActionOutput(out_port))
                self.add_flow(dp, 50, match, actions)
        
        # rate_str = 'unlimited' if ACTION_MAP[self.q_last_action][2] == 0xffff else f'{ACTION_MAP[self.q_last_action][2]/10}%'
            if out_port == CLOUD_PORT_BACKUP:
                rate_str = "unlimited"
            else:
    # mapping qid -> max_rate đúng theo _setup_queues()
                qid_to_rate = {0: 0xffff, 1: 700, 2: 500, 3: 300}
                rate = qid_to_rate.get(qid, 0xffff)
                rate_str = "unlimited" if rate == 0xffff else f"{rate/10}%"
                self.logger.info(f"{Colors.GREEN}[QL-APPLY] Cloud Egress Flow updated: Port {out_port}, Queue {qid if qid is not None else 'default'}, Rate {rate_str}.{Colors.RESET}")

    # --- Q-LEARNING CONTROL: TỰ ĐỘNG TỐI ƯU QUEUE ĐỂ GIẢM MẤT GÓI ---
    def run_qlearning_control(self):
        dpid = SW256_DPID
        if dpid not in self.datapaths:
            return

        dp = self.datapaths[dpid]
        current_port = self.q_last_port if self.q_last_port else CLOUD_PORT_MAIN
        current_qid = self.q_last_qid if self.q_last_qid is not None else 0
        load = self.q_port_load.get((dpid, current_port, current_qid))
        if load is None:
            load = self.q_port_load.get((dpid, current_port), 0)
        drops = self.q_drops.get((dpid, current_port, current_qid), 0)
        self.logger.info(f"[QL-OBS] dpid={dpid} port={current_port} qid={current_qid} loadBps={load:.1f} drops={drops}")


        state = self.model.get_state(load_bps=load, drops=drops)

        action = self.q_agent.choose_action(state)
        new_port, new_qid, rate = ACTION_MAP[action]

        stable_bonus = (self.q_last_action is not None and action == self.q_last_action)
        backup_penalty = (action == 3 and state != 2)  
        reward = self.model.get_reward(
        load_bps=load,
        drops=drops,
        stable_bonus=stable_bonus,
        backup_penalty=backup_penalty
        )
        if self.q_last_state is not None and self.q_last_action is not None:
            self.q_agent.learn(
                s=self.q_last_state,
                a=self.q_last_action,
                r=reward,
                s_next=state,
                load=load,
                drops=drops
            )
        else:
            if hasattr(self.q_agent, "_log_internal"):
                self.q_agent._log_internal(state=state, action=action, reward=reward, load=load, drops=drops, max_q=0.0)

        if self.q_last_action is None or action != self.q_last_action:
            self._update_cloud_flow(dp, new_port, new_qid)
            self.q_last_port = new_port
            self.q_last_qid = new_qid

    # In debug (giữ nguyên style log của bạn)
        rate_str = 'unlimited' if rate == 0xffff else f'{rate/10}%'
        print(
            f"{Colors.BLUE}[QL-STATUS] State:{state} → Action:{action} "
            f"(P{new_port} Q{new_qid if new_qid is not None else 'def'} {rate_str}) | "
            f"Load:{load/1e6:.2f}MB/s Drops:{drops} | Reward:{reward:+.1f} "
            f"ε:{self.q_agent.epsilon:.3f}{Colors.RESET}\n"
        )

        self.q_last_state = state
        self.q_last_action = action

        if int(time.time()) % 30 == 0:
            if hasattr(self.q_agent, "export_q_table"):
                self.q_agent.export_q_table()

    # --- FEATURE 3: API & PRE/POST FLOW LOGGING ---
    def change_route(self, dpid, destination_ip, new_port):
        if dpid not in self.datapaths: return False
        
        # NGĂN API thủ công thay đổi tuyến Cloud
        if destination_ip.startswith("10.0.100.") or destination_ip.startswith("10.0.200."):
             self.logger.warning(f"Manual change for {destination_ip} ignored: Q-Learning manages Cloud routing.")
             return False
        
        datapath = self.datapaths[dpid]
        parser = datapath.ofproto_parser
        
        # 1. Determine destination MAC
        dst_mac = self.static_arp_table.get(destination_ip)
        if not dst_mac and ("10.0.100" in destination_ip or "10.0.200" in destination_ip): 
            dst_mac = self.CLOUD_MAC
        if not dst_mac: return False

        # 2. Log "BEFORE" (Current State)
        # Note: Controller doesn't store old flows in RAM, we log the intent of change
        print(f"\n{Colors.YELLOW}--- [COMMAND RECEIVED] MODIFY FLOW ---{Colors.RESET}")
        print(f"Target Switch : {dpid}")
        print(f"Destination   : {destination_ip}")
        print(f"Old Action    : (Check Routing Table above)")
        print(f"{Colors.GREEN}New Action    : OUTPUT PORT {new_port}{Colors.RESET}")

        # 3. Install New Flow (Action)
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=destination_ip)
        actions = [
            parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
            parser.OFPActionSetField(eth_dst=dst_mac), 
            parser.OFPActionOutput(new_port)
        ]
        
        # Priority 100 to override default flow
        self.add_flow(datapath, 100, match, actions)
        
        print(f"{Colors.BLUE}--> Flow sent to switch successfully.{Colors.RESET}\n")
        return True

    # --- BASIC FUNCTIONS (KEPT AS IS) ---
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        
        if datapath.id == SW256_DPID:
            self._setup_queues(datapath)
            self._update_cloud_flow(datapath, CLOUD_PORT_MAIN, 0)  # Initial: Port 1, Queue 0

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP: return
        
        # Handle ARP
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocols(arp.arp)[0]
            if arp_pkt.opcode == arp.ARP_REQUEST:
                if arp_pkt.dst_ip.endswith('.254') or arp_pkt.dst_ip.endswith('.1'):
                    self.send_arp_reply(datapath, in_port, arp_pkt.src_mac, self.GATEWAY_MAC, arp_pkt.dst_ip, arp_pkt.src_ip)
                else: self.do_flood(datapath, msg, in_port)
            else: self.do_flood(datapath, msg, in_port)
            return

        # Handle IP Routing
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocols(ipv4.ipv4)[0]
            self.handle_ip_routing(datapath, in_port, ip_pkt, msg)

    def handle_ip_routing(self, datapath, in_port, ip_pkt, msg):
        dpid = datapath.id
        dst_ip = ip_pkt.dst
        
        if dpid in self.routing_table:
            subnet_key = ".".join(dst_ip.split('.')[:3])
            routing_table = self.routing_table.get(dpid, {})
            out_port = routing_table.get(subnet_key)
            if not out_port: out_port = routing_table.get("default")
            
            if out_port:
                dst_mac = self.static_arp_table.get(dst_ip)
                if not dst_mac and ("10.0.100" in dst_ip or "10.0.200" in dst_ip): dst_mac = self.CLOUD_MAC

                if dst_mac:
                    parser = datapath.ofproto_parser
                    actions = []
                    # Default Failover Logic (Priority 10)
                    if dpid == 256 and ("10.0.100" in dst_ip): # G1
                        group_id = 50
                        if dpid not in self.groups_installed:
                            self.add_failover_group(datapath, group_id, 1, 5)
                            self.groups_installed[dpid] = True
                        actions = [parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                                   parser.OFPActionSetField(eth_dst=dst_mac),
                                   parser.OFPActionGroup(group_id)]
                    elif dpid == 768 and ("10.0.200" in dst_ip): # G3
                        group_id = 51
                        if dpid not in self.groups_installed:
                            self.add_failover_group(datapath, group_id, 3, 1)
                            self.groups_installed[dpid] = True
                        actions = [parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                                   parser.OFPActionSetField(eth_dst=dst_mac),
                                   parser.OFPActionGroup(group_id)]
                    else:
                        actions = [parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                                   parser.OFPActionSetField(eth_dst=dst_mac),
                                   parser.OFPActionOutput(out_port)]
                    
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst_ip)
                    self.add_flow(datapath, 10, match, actions)
                    
                    data = msg.data if msg.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None
                    out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data)
                    datapath.send_msg(out)
                else: self.do_flood(datapath, msg, in_port)
            else: self.do_flood(datapath, msg, in_port)
        else: self.do_flood(datapath, msg, in_port)

    def add_failover_group(self, datapath, group_id, main_port, backup_port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions_main = [parser.OFPActionOutput(main_port)]
        bucket_main = parser.OFPBucket(watch_port=main_port, watch_group=ofproto.OFPG_ANY, actions=actions_main)
        actions_backup = [parser.OFPActionOutput(backup_port)]
        bucket_backup = parser.OFPBucket(watch_port=backup_port, watch_group=ofproto.OFPG_ANY, actions=actions_backup)
        req = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_FF, group_id, [bucket_main, bucket_backup])
        datapath.send_msg(req)
        self.logger.info(f"Failover Group {group_id} added on SW {datapath.id}")

    def send_arp_reply(self, datapath, port, dst_mac, src_mac, src_ip, dst_ip):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP, dst=dst_mac, src=src_mac))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=src_mac, src_ip=src_ip, dst_mac=dst_mac, dst_ip=dst_ip))
        pkt.serialize()
        actions = [parser.OFPActionOutput(port)]
        datapath.send_msg(parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER, in_port=ofproto.OFPP_CONTROLLER, actions=actions, data=pkt.data))

    def do_flood(self, datapath, msg, in_port):
        actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
        datapath.send_msg(datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data))

class RestRouterController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(RestRouterController, self).__init__(req, link, data, **config)
        self.app = data[simple_switch_instance_name]

    @route('router', url, methods=['POST'], requirements={'dpid': '[0-9]+'})
    def set_route(self, req, **kwargs):
        dpid = int(kwargs['dpid'])
        try: body = req.json if req.body else {}
        except ValueError: return Response(status=400, body=b"Invalid JSON")
        success = self.app.change_route(dpid, body.get('dest'), int(body.get('port')))
        return Response(status=200, body=b"Route Changed") if success else Response(status=404, body=b"Failed")