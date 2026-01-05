import json
import time
import pprint
from operator import attrgetter
from typing import Optional
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, ether_types, tcp, udp
from ryu.lib import hub
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
import os
import requests
import numpy as np
import random

# --- CONFIGURATION ---
CONGESTION_THRESHOLD = 200000 
MONITOR_INTERVAL = 2

SW256_DPID = 256
CLOUD_PORT_MAIN = 1
CLOUD_PORT_BACKUP = 5

CRIT_UDP = int(os.environ.get("CRIT_UDP", "5001"))
TEL_UDP = int(os.environ.get("TEL_UDP", "5002"))
BULK_TCP = int(os.environ.get("BULK_TCP", "5003"))

QUEUE_PRIO = 0
QUEUE_BULK = 1
METER_BULK_ID = 1

# QoS Profiles for bulk traffic: (queue_id, meter_rate_kbps)
QOS_PROFILES = [
    (1, 800),   # Queue 1, 800 Kbps meter
    (1, 1200),  # Queue 1, 1200 Kbps meter  
    (1, 1600),  # Queue 1, 1600 Kbps meter
    (2, 800),   # Queue 2, 800 Kbps meter
    (2, 1200),  # Queue 2, 1200 Kbps meter
    (2, 1600),  # Queue 2, 1600 Kbps meter
]

# --- LOCAL Q-LEARNING IMPLEMENTATION ---
class QoSModel:
    def __init__(self, congestion_threshold: float):
        self.th = float(congestion_threshold)

    def get_state(self, load_bps: float, drops: int) -> int:
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0
        try:
            d = int(drops)
        except Exception:
            d = 0
        if d > 0:
            return 2
        if load < 0.5 * self.th:
            return 0
        elif load < 1.0 * self.th:
            return 1
        else:
            return 2

    def get_reward(self, load_bps: float, drops: int) -> float:
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0
        try:
            d = int(drops)
        except Exception:
            d = 0
        
        if d > 0:
            return -10.0  # Strong penalty for drops
        elif load < 0.5 * self.th:
            return 1.0    # Reward for low load
        elif load < 1.0 * self.th:
            return 0.0    # Neutral for medium load
        else:
            return -2.0   # Penalty for high load

class QAgent:
    def __init__(self, n_states, n_actions, lr=0.1, gamma=0.9, epsilon=1.0, epsilon_min=0.05, epsilon_decay=0.995):
        self.n_states = n_states
        self.n_actions = n_actions
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.step = 0
        self.q_table = np.zeros((n_states, n_actions))

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, self.n_actions - 1)
        return int(np.argmax(self.q_table[state]))

    def learn(self, state, action, reward, next_state):
        current_q = self.q_table[state][action]
        max_next_q = np.max(self.q_table[next_state])
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action] = new_q
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        self.step += 1

# --- CONFIGURATION ---
CONGESTION_THRESHOLD = 200000 
MONITOR_INTERVAL = 2            # Monitor every 2 seconds

SW256_DPID = 256
CLOUD_PORT_MAIN = 1
CLOUD_PORT_BACKUP = 5

CRIT_UDP = int(os.environ.get("CRIT_UDP", "5001"))
TEL_UDP = int(os.environ.get("TEL_UDP", "5002"))
BULK_TCP = int(os.environ.get("BULK_TCP", "5003"))

QUEUE_PRIO = 0
QUEUE_BULK = 1
METER_BULK_ID = 1

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
        self.logger.info(f"{Colors.GREEN}--> [SYSTEM] Controller V3 with Local Q-Learning Ready.{Colors.RESET}")
        
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

        self.agent_url = os.environ.get("QLEARNING_AGENT_URL", "http://qlearning-agent:5000").rstrip("/")
        self.agent_timeout_s = float(os.environ.get("QLEARNING_AGENT_TIMEOUT_S", "0.3"))
        self._agent_session = requests.Session()

        self.last_agent_choice = {}
        
        # Meter management for dynamic QoS
        self._meters_installed = set()
        self._meter_key_to_id = {}
        self._next_meter_id = 10
        self.flow_idle_timeout = int(os.environ.get("FLOW_IDLE_TIMEOUT", "20"))
        self.flow_hard_timeout = int(os.environ.get("FLOW_HARD_TIMEOUT", "0"))

        # Initialize local Q-learning
        self.model = QoSModel(CONGESTION_THRESHOLD)
        self.agent = QAgent(n_states=3, n_actions=len(QOS_PROFILES), epsilon=float(os.environ.get("EPSILON", "0.1")))
        self._flow_states = {}  # Track state per flow
        self._flow_actions = {}  # Track last action per flow

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
                "10.0.100": 1, "10.0.200": 5, 
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

    def _agent_observe(self, dpid: int, port: int, load_bps: float, drops: int, qid: Optional[int] = None):
        try:
            self._agent_session.post(
                f"{self.agent_url}/observe",
                json={
                    "dpid": int(dpid),
                    "port": int(port),
                    "qid": (None if qid is None else int(qid)),
                    "load_bps": float(load_bps),
                    "drops": int(drops),
                },
                timeout=self.agent_timeout_s,
            )
        except Exception:
            return

    def _agent_choose_out_port(self, dpid: int, dst_prefix: str, candidates):
        try:
            candidate_actions = []
            action_idx = 0
            local_action_map = {}
            for port in candidates:
                for queue_id, meter_rate in QOS_PROFILES:
                    local_action_map[int(action_idx)] = (int(port), int(queue_id), int(meter_rate))
                    candidate_actions.append(
                        {
                            "action_idx": int(action_idx),
                            "out_port": int(port),
                            "queue_id": int(queue_id),
                            "meter_rate_kbps": int(meter_rate),
                        }
                    )
                    action_idx += 1

            resp = self._agent_session.post(
                f"{self.agent_url}/act",
                json={"dpid": int(dpid), "dst_prefix": str(dst_prefix), "candidates": candidate_actions},
                timeout=self.agent_timeout_s,
            )
            if resp.status_code != 200:
                return None
            data = resp.json() if resp.content else {}

            chosen_action_idx = data.get("action")
            out_port = data.get("out_port")
            queue_id = data.get("queue_id")
            meter_rate = data.get("meter_rate_kbps")

            if out_port is None or queue_id is None or meter_rate is None:
                action_details = local_action_map.get(int(chosen_action_idx)) if chosen_action_idx is not None else None
                if not action_details:
                    return None
                out_port, queue_id, meter_rate = action_details
            else:
                out_port, queue_id, meter_rate = int(out_port), int(queue_id), int(meter_rate)

            try:
                self.last_agent_choice[f"{int(dpid)}:{dst_prefix}"] = {
                    "ts": time.time(),
                    "dpid": int(dpid),
                    "dst_prefix": str(dst_prefix),
                    "candidates": [int(p) for p in list(candidates)],
                    "out_port": int(out_port),
                    "queue_id": int(queue_id),
                    "meter_rate_kbps": int(meter_rate),
                    "state": data.get("state"),
                    "action": (None if chosen_action_idx is None else int(chosen_action_idx)),
                    "epsilon": data.get("epsilon"),
                    "step": data.get("step"),
                }
            except Exception:
                pass

            return int(out_port), int(queue_id), int(meter_rate)
        except Exception:
            return None

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
                    if dp.id in [256, 512, 768]:
                        self._request_stats(dp)
                hub.sleep(0.3)
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
            rx_dropped = getattr(stat, "rx_dropped", 0)
            tx_dropped = getattr(stat, "tx_dropped", 0)
            
            if key in self.prev_stats:
                prev = self.prev_stats[key]
                if isinstance(prev, tuple) and len(prev) >= 5:
                    prev_rx, prev_tx, prev_rx_dropped, prev_tx_dropped, prev_time = prev[:5]
                else:
                    prev_rx, prev_tx, prev_time = prev
                    prev_rx_dropped, prev_tx_dropped = 0, 0
                duration = time.time() - prev_time
                if duration > 0:
                    speed_tx = (tx_bytes - prev_tx) / duration
                    speed_rx = (rx_bytes - prev_rx) / duration
                    total_speed = speed_tx + speed_rx
                    drops = int((rx_dropped - prev_rx_dropped) + (tx_dropped - prev_tx_dropped))
                    if drops < 0:
                        drops = 0
                    
                    self.q_port_load[key] = total_speed
                    self.q_drops[key] = drops

                    self._agent_observe(dpid=dpid, port=port_no, qid=None, load_bps=total_speed, drops=drops)
                    
                    # RED ALERT LOGIC
                    if speed_tx > CONGESTION_THRESHOLD or speed_rx > CONGESTION_THRESHOLD:
                        max_speed = max(speed_tx, speed_rx) / 1000000
                        print(f"{Colors.RED}[!] CONGESTION ALERT: Switch {dpid} Port {port_no} | Load: {max_speed:.2f} MB/s{Colors.RESET}")
            
            self.prev_stats[key] = (rx_bytes, tx_bytes, rx_dropped, tx_dropped, time.time())

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

                    self._agent_observe(dpid=dpid, port=port_no, qid=queue_id, load_bps=speed, drops=drops)
                    
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
        return

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

        bulk_kbps = int(os.environ.get("BULK_METER_KBPS", "1200"))
        self.add_meter(datapath, meter_id=METER_BULK_ID, rate_kbps=bulk_kbps, burst_kb=200)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=int(idle_timeout),
            hard_timeout=int(hard_timeout),
        )
        datapath.send_msg(mod)

    def add_flow_with_meter(self, datapath, priority, match, actions, meter_id, buffer_id=None, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [
            parser.OFPInstructionMeter(int(meter_id), ofproto.OFPIT_METER),
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=int(idle_timeout),
            hard_timeout=int(hard_timeout),
        )
        datapath.send_msg(mod)

    def add_meter(self, datapath, meter_id, rate_kbps, burst_kb=100):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        bands = [parser.OFPMeterBandDrop(rate=int(rate_kbps), burst_size=int(burst_kb))]
        req = parser.OFPMeterMod(
            datapath=datapath,
            command=ofproto.OFPMC_ADD,
            flags=ofproto.OFPMF_KBPS,
            meter_id=int(meter_id),
            bands=bands,
        )
        datapath.send_msg(req)

    def _ensure_meter(self, datapath, rate_kbps: int):
        key = (int(datapath.id), int(rate_kbps))
        meter_id = self._meter_key_to_id.get(key)
        if meter_id is None:
            meter_id = int(self._next_meter_id)
            self._next_meter_id += 1
            self._meter_key_to_id[key] = int(meter_id)

        if key not in self._meters_installed:
            try:
                self.add_meter(datapath, meter_id=int(meter_id), rate_kbps=int(rate_kbps), burst_kb=200)
                self._meters_installed.add(key)
            except Exception:
                pass
        return int(meter_id)

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
            tcp_pkt = pkt.get_protocol(tcp.tcp)
            udp_pkt = pkt.get_protocol(udp.udp)

            l4_proto = None
            l4_dst_port = None
            if tcp_pkt is not None:
                l4_proto = "tcp"
                l4_dst_port = int(tcp_pkt.dst_port)
            elif udp_pkt is not None:
                l4_proto = "udp"
                l4_dst_port = int(udp_pkt.dst_port)

            self.handle_ip_routing(datapath, in_port, ip_pkt, msg, l4_proto=l4_proto, l4_dst_port=l4_dst_port)

    def handle_ip_routing(self, datapath, in_port, ip_pkt, msg, l4_proto=None, l4_dst_port=None):
        dpid = datapath.id
        dst_ip = ip_pkt.dst
        
        if dpid in self.routing_table:
            subnet_key = ".".join(dst_ip.split('.')[:3])
            routing_table = self.routing_table.get(dpid, {})
            out_port = routing_table.get(subnet_key)
            if not out_port: out_port = routing_table.get("default")

            candidates = []
            # Cloud routing on G1 must be deterministic to avoid loops:
            # - 10.0.100.* goes out g1 port 1 (direct to cloud-eth0)
            # - 10.0.200.* goes out g1 port 5 (toward g3, then cloud-eth1)
            if dpid == 256 and subnet_key == "10.0.100":
                candidates = [int(CLOUD_PORT_MAIN)]
                out_port = int(CLOUD_PORT_MAIN)
            elif dpid == 256 and subnet_key == "10.0.200":
                candidates = [int(CLOUD_PORT_BACKUP)]
                out_port = int(CLOUD_PORT_BACKUP)
            else:
                primary = routing_table.get(subnet_key)
                if primary is not None:
                    candidates.append(int(primary))
                else:
                    default_p = routing_table.get("default")
                    if default_p is not None:
                        candidates.append(int(default_p))

            chosen_queue_id = None
            chosen_meter_rate = None
            if (l4_dst_port == BULK_TCP) and (l4_proto in ["tcp", "udp"]):
                agent_out = self._agent_choose_out_port(dpid=dpid, dst_prefix=subnet_key, candidates=candidates)
                if agent_out is not None:
                    out_port, chosen_queue_id, chosen_meter_rate = agent_out
            
            if out_port:
                dst_mac = self.static_arp_table.get(dst_ip)
                if not dst_mac and ("10.0.100" in dst_ip or "10.0.200" in dst_ip): dst_mac = self.CLOUD_MAC

                if dst_mac:
                    parser = datapath.ofproto_parser
                    actions = []
                    # Default Failover Logic (Priority 10)
                    actions = [parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                               parser.OFPActionSetField(eth_dst=dst_mac)]

                    use_meter = False
                    if l4_proto == "udp" and l4_dst_port in [CRIT_UDP, TEL_UDP]:
                        actions.append(parser.OFPActionSetQueue(QUEUE_PRIO))
                    elif (l4_dst_port == BULK_TCP) and (l4_proto in ["tcp", "udp"]):
                        use_meter = True
                        if chosen_queue_id is not None:
                            actions.append(parser.OFPActionSetQueue(int(chosen_queue_id)))
                        else:
                            actions.append(parser.OFPActionSetQueue(QUEUE_BULK))

                    actions.append(parser.OFPActionOutput(out_port))
                    
                    if l4_proto == "udp" and l4_dst_port is not None:
                        match = parser.OFPMatch(
                            eth_type=ether_types.ETH_TYPE_IP,
                            ip_proto=17,
                            ipv4_dst=dst_ip,
                            udp_dst=int(l4_dst_port),
                        )
                    elif l4_proto == "tcp" and l4_dst_port is not None:
                        match = parser.OFPMatch(
                            eth_type=ether_types.ETH_TYPE_IP,
                            ip_proto=6,
                            ipv4_dst=dst_ip,
                            tcp_dst=int(l4_dst_port),
                        )
                    else:
                        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst_ip)

                    meter_id = None
                    if use_meter:
                        if chosen_meter_rate is not None:
                            meter_id = self._ensure_meter(datapath, rate_kbps=int(chosen_meter_rate))
                        else:
                            meter_id = int(METER_BULK_ID)
                        self.add_flow_with_meter(
                            datapath,
                            20,
                            match,
                            actions,
                            meter_id=int(meter_id),
                            idle_timeout=self.flow_idle_timeout,
                            hard_timeout=self.flow_hard_timeout,
                        )
                    else:
                        self.add_flow(
                            datapath,
                            20,
                            match,
                            actions,
                            idle_timeout=self.flow_idle_timeout,
                            hard_timeout=self.flow_hard_timeout,
                        )
                    
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

    @route('qos', '/qos/routing', methods=['GET'])
    def get_routing(self, req, **kwargs):
        body = json.dumps(self.app.routing_table)
        return Response(content_type='application/json', body=body.encode('utf-8'))

    @route('qos', '/qos/agent', methods=['GET'])
    def get_agent_state(self, req, **kwargs):
        body = json.dumps(self.app.last_agent_choice)
        return Response(content_type='application/json', body=body.encode('utf-8'))

    @route('qos', '/qos/snapshot', methods=['GET'])
    def get_snapshot(self, req, **kwargs):
        port_load = {f"{k[0]}:{k[1]}": float(v) for k, v in self.app.q_port_load.items() if isinstance(k, tuple) and len(k) == 2}
        queue_load = {f"{k[0]}:{k[1]}:{k[2]}": float(v) for k, v in self.app.q_port_load.items() if isinstance(k, tuple) and len(k) == 3}
        queue_drops = {f"{k[0]}:{k[1]}:{k[2]}": int(v) for k, v in self.app.q_drops.items() if isinstance(k, tuple) and len(k) == 3}
        body = json.dumps({"ts": time.time(), "port_load": port_load, "queue_load": queue_load, "queue_drops": queue_drops})
        return Response(content_type='application/json', body=body.encode('utf-8'))

    @route('router', url, methods=['POST'], requirements={'dpid': '[0-9]+'})
    def set_route(self, req, **kwargs):
        dpid = int(kwargs['dpid'])
        try: body = req.json if req.body else {}
        except ValueError: return Response(status=400, body=b"Invalid JSON")
        success = self.app.change_route(dpid, body.get('dest'), int(body.get('port')))
        return Response(status=200, body=b"Route Changed") if success else Response(status=404, body=b"Failed")