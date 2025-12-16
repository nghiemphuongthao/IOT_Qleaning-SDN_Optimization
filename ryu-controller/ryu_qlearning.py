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
from q_agent import QAgent


# --- CẤU HÌNH LOAD BALANCING VÀ OFP ---
ACTION_MAP = {
    0: (100, 0),    # 100% qua Port 1
    1: (70, 30),     # 70% qua Port 1, 30% qua Port 5
    2: (50, 50),     # 50% qua Port 1, 50% qua Port 5
    3: (0, 100)      # 100% qua Port 5
}
SW256_DPID = 256
CLOUD_PORT_MAIN = 1
CLOUD_PORT_BACKUP = 5
GROUP_ID = 100 # ID của Group Select cho Load Balancing

# --- CONFIGURATION ---
CONGESTION_THRESHOLD = 4000000  # 4MB/s ~ 32Mbps (Warning Threshold)
MONITOR_INTERVAL = 5            # Giám sát và điều khiển mỗi 5 giây

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
        self.logger.info(f"{Colors.GREEN}--> [SYSTEM] Anti-Loop + RL Controller Ready.{Colors.RESET}")
        
        wsgi = kwargs['wsgi']
        wsgi.register(RestRouterController, {simple_switch_instance_name: self})

        self.GATEWAY_MAC = "00:00:00:00:01:00"
        self.CLOUD_MAC   = "00:00:00:00:00:FF" 
        
        self.datapaths = {}
        self.groups_installed = set()  # Dùng set để theo dõi Group ID đã được cài đặt
        self.prev_stats = {} 
        self.q_port_load = {}      # Lưu tốc độ port cho Q-Learning

        # Biến Q-Learning
        self.q_agent = QAgent(n_states=3, n_actions=4)  # 3 trạng thái, 4 hành động chia tải
        self.q_last_state = None
        self.q_last_action = None
        
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
            256: { "10.0.100": 1, "10.0.200": 1, "10.0.1": 2, "10.0.2": 3, "10.0.3": 4, "10.0.4": 5 },
            512: { "10.0.3": 2, "default": 1 },
            768: { "10.0.4": 2, "10.0.100": 1, "10.0.200": 3, "default": 1 }
        }
        self.print_routing_table_pretty()

        # Khởi động thread giám sát + điều khiển Q-Learning
        self.monitor_thread = hub.spawn(self._monitor_and_control)

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

    # --- MONITOR & Q-LEARNING CONTROL THREAD ---
    def _monitor_and_control(self):
        while True:
            for dp in list(self.datapaths.values()):
                if dp.id in [256, 768]:
                    self._request_stats(dp)
            self.run_qlearning_control()
            hub.sleep(MONITOR_INTERVAL)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
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
                if duration > 1:
                    speed_tx = (tx_bytes - prev_tx) / duration
                    speed_rx = (rx_bytes - prev_rx) / duration
                    total_speed = speed_tx + speed_rx
                    
                    self.q_port_load[key] = total_speed

                    if dpid == SW256_DPID and (port_no == CLOUD_PORT_MAIN or port_no == CLOUD_PORT_BACKUP):
                        print(f"{Colors.YELLOW}[STATS-DEBUG] SW{dpid} P{port_no}: {total_speed/1e6:.3f} MB/s (State: {self.q_agent.get_best_action(self.q_last_state) if self.q_last_state is not None else 'N/A'}){Colors.RESET}")
                        
                    if total_speed > CONGESTION_THRESHOLD:
                        print(f"{Colors.RED}[!] CONGESTION: SW{dpid} Port {port_no} | {total_speed/1e6:.2f} MB/s{Colors.RESET}")
            
            # Luôn cập nhật trạng thái thống kê hiện tại            
            self.prev_stats[key] = (rx_bytes, tx_bytes, time.time())

    # ================= CƠ CHẾ GROUP SELECT CHO LOAD BALANCING =================
    def _install_lb_group(self, w1, w5):
        """
        Cài đặt (ADD) hoặc Sửa đổi (MODIFY) Group Select ID 100 trên SW256
        để chia tải theo tỷ lệ w1:w5.
        """
        dpid = SW256_DPID
        if dpid not in self.datapaths:
            self.logger.warning(f"[GROUP] SW{dpid} not connected.")
            return

        dp = self.datapaths[dpid]
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        gid = GROUP_ID

        buckets = []
        if w1 > 0:
            buckets.append(parser.OFPBucket(
                weight=w1, 
                watch_port=CLOUD_PORT_MAIN,
                actions=[parser.OFPActionOutput(CLOUD_PORT_MAIN)]
            ))
        
        if w5 > 0:
            buckets.append(parser.OFPBucket(
                weight=w5, 
                watch_port=CLOUD_PORT_BACKUP,
                actions=[parser.OFPActionOutput(CLOUD_PORT_BACKUP)]
            ))
        
        # Dùng ADD nếu mới, MODIFY nếu đã tồn tại.
        cmd = ofp.OFPGC_ADD if gid not in self.groups_installed else ofp.OFPGC_MODIFY
        
        dp.send_msg(parser.OFPGroupMod(
            datapath=dp, 
            command=cmd, 
            type_=ofp.OFPGT_SELECT, 
            group_id=gid, 
            buckets=buckets))
            
        self.groups_installed.add(gid)

        # Cài Flow chỉ định Group sau khi Group được tạo
        if cmd == ofp.OFPGC_ADD:
            self._install_cloud_flow(dp)
        
        self.logger.info(f"{Colors.GREEN}[QL-APPLY] Group ID {gid} {cmd == ofp.OFPGC_ADD and 'ADDED' or 'MODIFIED'}. Split P{CLOUD_PORT_MAIN}={w1}% P{CLOUD_PORT_BACKUP}={w5}%{Colors.RESET}")
        
    def _install_cloud_flow(self, dp):
        """
        Cài đặt Flow tĩnh (Prio 50) để chuyển tiếp traffic Cloud sang Group ID 100.
        (Thay thế hàm apply_dynamic_cloud_route cũ)
        """
        parser = dp.ofproto_parser
        
        # Flow cho 10.0.100.0/24 và 10.0.200.0/24
        for subnet in ["10.0.100.0/24", "10.0.200.0/24"]:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=subnet)
            actions = [
                parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                parser.OFPActionSetField(eth_dst=self.CLOUD_MAC),
                parser.OFPActionGroup(GROUP_ID) # Hành động: chuyển sang Group 100
            ]
            self.add_flow(dp, 50, match, actions) 
            
        self.logger.info(f"{Colors.GREEN}[QL-APPLY] Cloud Egress Flow installed/updated to use Group {GROUP_ID}.{Colors.RESET}")


    # --- Q-LEARNING CONTROL: TỰ ĐỘNG TỐI ƯU LOAD BALANCING ---
    def run_qlearning_control(self):
        dpid = SW256_DPID
        if dpid not in self.datapaths:
            return

        load_p1 = self.q_port_load.get((dpid, CLOUD_PORT_MAIN), 0)
        load_p5 = self.q_port_load.get((dpid, CLOUD_PORT_BACKUP), 0)
        total_load = load_p1 + load_p5

        # 1. Xác định state (Dùng ngưỡng tối ưu)
        if total_load < CONGESTION_THRESHOLD * 0.5:
            state = 0  # Low (< 2MB/s)
        elif total_load < CONGESTION_THRESHOLD * 1.1:
            state = 1  # Medium (2MB/s - 4.4MB/s)
        else:
            state = 2  # High (>= 4.4MB/s)

        # 2. Agent chọn hành động (Action là index từ 0-3)
        action = self.q_agent.choose_action(state)
        w1, w5 = ACTION_MAP[action] # Lấy tỷ lệ chia tải
        
        # 3. Tính reward (Tối ưu hóa để giảm Loss, tăng ổn định và cân bằng)
        max_load = max(load_p1, load_p5)
        imbalance = abs(load_p1 - load_p5) / (total_load + 1e-6) # Độ mất cân bằng
        
        # Thưởng/Phạt cơ bản dựa trên tải tối đa (Max Load)
        if max_load > CONGESTION_THRESHOLD:
            reward = -50  # Phạt nặng vì quá tải là nguyên nhân chính gây mất gói
        elif max_load < CONGESTION_THRESHOLD * 0.5:
            reward = 30   # Rất tốt: Load thấp hơn 50% ngưỡng
        elif max_load < CONGESTION_THRESHOLD:
            reward = 10   # Tốt: Load chấp nhận được
        else:
            reward = -5   # Load vừa chạm ngưỡng (cảnh báo)

        # Thưởng cho sự ổn định và cân bằng
        if self.q_last_action is not None and action == self.q_last_action:
            reward += 5 # Thưởng thêm nếu Agent quyết định giữ nguyên Action (chống dao động)
            
        # Thưởng cho cân bằng tải (Chỉ quan trọng khi tải > 0)
        if total_load > 1e6: # Nếu có tải đáng kể (1MB/s)
            reward += (5 * (1 - imbalance)) # Thưởng tối đa 5 điểm nếu cân bằng hoàn hảo
        
        if state == 0 and total_load > 0.5e6: # Nếu tải thấp nhưng có traffic
             if action == 2: # Hành động 50:50
                 reward += 3 # Thưởng nhẹ vì chia tải là hành động an toàn nhất
             elif action == 0 or action == 3: # Hành động 100:0 hoặc 0:100 (rủi ro cao hơn)
                 reward -= 2 # Phạt nhẹ vì chọn đường đơn khi có 2 đường khỏe

        # 4. Học
        if self.q_last_state is not None:
            self.q_agent.learn(self.q_last_state, self.q_last_action, reward, state)

        # 5. Áp dụng Action (Group Mod)
        if self.q_last_action is None or action != self.q_last_action or GROUP_ID not in self.groups_installed:
            self._install_lb_group(w1, w5)

        # In thông tin
        self.q_agent.print_q_table()
        print(f"{Colors.BLUE}[QL-STATUS] State:{state} → Action:{action} ({w1}:{w5}) | "
              f"P1:{load_p1/1e6:.2f}MB/s P5:{load_p5/1e6:.2f}MB/s | "
              f"Reward:{reward:+.1f} ε:{self.q_agent.epsilon:.3f}{Colors.RESET}\n")

        self.q_last_state = state
        self.q_last_action = action


    # --- REST API: THAY ĐỔI ROUTE THỦ CÔNG (override Q-Learning) ---
    def change_route(self, dpid, destination_ip, new_port):
        if dpid not in self.datapaths: return False
        
        # NGĂN API thủ công thay đổi tuyến Cloud
        if destination_ip.startswith("10.0.100.") or destination_ip.startswith("10.0.200."):
             self.logger.warning(f"Manual change for {destination_ip} ignored: Q-Learning manages Cloud routing.")
             return False
             
        datapath = self.datapaths[dpid]
        parser = datapath.ofproto_parser
        
        dst_mac = self.static_arp_table.get(destination_ip) or self.CLOUD_MAC
        
        print(f"\n{Colors.YELLOW}--- [MANUAL ROUTE CHANGE] ---{Colors.RESET}")
        print(f"Switch: {dpid} | Dest: {destination_ip} → Port {new_port}")

        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=destination_ip)
        actions = [
            parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
            parser.OFPActionSetField(eth_dst=dst_mac),
            parser.OFPActionOutput(new_port)
        ]
        self.add_flow(datapath, 100, match, actions)  # Priority cao nhất
        print(f"{Colors.BLUE}--> Manual flow installed.{Colors.RESET}\n")
        return True

    # --- CÁC HÀM CƠ BẢN (KHÔNG THAY ĐỔI) ---
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

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
        
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocols(arp.arp)[0]
            if arp_pkt.opcode == arp.ARP_REQUEST:
                if arp_pkt.dst_ip.endswith('.254') or arp_pkt.dst_ip.endswith('.1'):
                    self.send_arp_reply(datapath, in_port, arp_pkt.src_mac, self.GATEWAY_MAC, arp_pkt.dst_ip, arp_pkt.src_ip)
                else:
                    self.do_flood(datapath, msg, in_port)
            else:
                self.do_flood(datapath, msg, in_port)
            return

        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocols(ipv4.ipv4)[0]
            self.handle_ip_routing(datapath, in_port, ip_pkt, msg)

    def handle_ip_routing(self, datapath, in_port, ip_pkt, msg):
        dpid = datapath.id
        dst_ip = ip_pkt.dst
        
        subnet_key = ".".join(dst_ip.split('.')[:3])
        routing_table = self.routing_table.get(dpid, {})
        out_port = routing_table.get(subnet_key) or routing_table.get("default")
        
        if not out_port:
            self.do_flood(datapath, msg, in_port)
            return

        dst_mac = self.static_arp_table.get(dst_ip) or self.CLOUD_MAC

        parser = datapath.ofproto_parser
        actions = [
            parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
            parser.OFPActionSetField(eth_dst=dst_mac),
            parser.OFPActionOutput(out_port)
        ]

        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst_ip)
        self.add_flow(datapath, 10, match, actions)

        data = msg.data if msg.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def send_arp_reply(self, datapath, port, dst_mac, src_mac, src_ip, dst_ip):
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP,
                                           dst=dst_mac, src=src_mac))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=src_mac, src_ip=src_ip,
                                 dst_mac=dst_mac, dst_ip=dst_ip))
        pkt.serialize()
        actions = [parser.OFPActionOutput(port)]
        datapath.send_msg(parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                             in_port=datapath.ofproto.OFPP_CONTROLLER,
                                             actions=actions, data=pkt.data))

    def do_flood(self, datapath, msg, in_port):
        actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
        datapath.send_msg(datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=msg.data))


class RestRouterController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(RestRouterController, self).__init__(req, link, data, **config)
        self.app = data[simple_switch_instance_name]

    @route('router', url, methods=['POST'], requirements={'dpid': '[0-9]+'})
    def set_route(self, req, **kwargs):
        dpid = int(kwargs['dpid'])
        try:
            body = req.json if req.body else {}
        except ValueError:
            return Response(status=400, body=b"Invalid JSON")
        
        dest = body.get('dest')
        port = body.get('port')
        if not dest or not port:
            return Response(status=400, body=b"Missing dest or port")
        
        success = self.app.change_route(dpid, dest, int(port))
        return Response(status=200, body=b"Route Changed") if success else Response(status=404, body=b"Failed")