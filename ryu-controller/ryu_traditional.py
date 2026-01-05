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

MONITOR_INTERVAL = 2             

simple_switch_instance_name = 'simple_switch_api_app'
url = '/router/{dpid}'


PORT_CAPACITY = {
    # Switch G1 (dpid=256)
    (256, 1): 1.5,   # G1 -> Cloud (Main Path): Max 1.5 Mbps
    (256, 5): 50.0,  # G1 -> G3 (Backup Path): 50 Mbps
    
    # Switch G3 (dpid=768)
    (768, 3): 10.0,  # G3 -> Cloud: 10 Mbps
    (768, 1): 50.0,  # G3 -> G1
}

DEFAULT_CAPACITY = 10.0 

# ANSI color codes
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
        self.logger.info(f"{Colors.GREEN}--> [SYSTEM] Auto-Reroute Controller Ready (Fixed Ping).{Colors.RESET}")
        
        wsgi = kwargs['wsgi']
        wsgi.register(RestRouterController, {simple_switch_instance_name: self})

        self.GATEWAY_MAC = "00:00:00:00:01:00" # MAC Ao cua Gateway
        self.CLOUD_MAC   = "00:00:00:00:00:FF" # MAC Gia lap cua Cloud
        
        self.datapaths = {}
        self.mac_to_port = {}  # Them lai bang MAC de ho tro L2 Switching
        self.prev_stats = {} 
        self.rerouted_flags = {} 

        self.monitor_thread = hub.spawn(self._monitor)

        # Static ARP Table (De controller biet MAC dich ma khong can flood)
        self.static_arp_table = {
            "10.0.100.2": self.CLOUD_MAC,
            "10.0.200.2": self.CLOUD_MAC,
            "10.0.1.1": "00:00:00:00:00:01", "10.0.1.2": "00:00:00:00:00:02",
            "10.0.1.3": "00:00:00:00:00:03", "10.0.2.4": "00:00:00:00:00:04",
            "10.0.2.5": "00:00:00:00:00:05", "10.0.3.6": "00:00:00:00:00:06",
            "10.0.3.7": "00:00:00:00:00:07", "10.0.4.8": "00:00:00:00:00:08",
            "10.0.4.9": "00:00:00:00:00:09", "10.0.4.10": "00:00:00:00:00:0a",
        }
        
        # Gateway IPs can tra loi ARP
        self.GW_IPS = [
            '10.0.1.254', '10.0.2.254', '10.0.3.254', '10.0.4.254',
            '10.0.100.1', '10.0.200.1'
        ]

        # --- STATIC ROUTING TABLE (Normal State) ---
        self.routing_table = {
            256: { # G1
                "10.0.100": 1, # Default: To Cloud via Port 1
                "10.0.200": 1, 
                "10.0.1": 2, "10.0.2": 3, 
                "10.0.3": 4, "10.0.4": 5
            },
            512: { "10.0.3": 2, "default": 1 }, # G2
            768: { # G3
                "10.0.4": 2,
                "10.0.100": 3, 
                "10.0.200": 3, 
                "default": 1    
            }
        }
        self.print_routing_table_pretty()

    def print_routing_table_pretty(self):
        print(f"\n{Colors.BLUE}{'='*60}")
        print(f"{'CURRENT ROUTING TABLE':^60}")
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

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                if dp.id in [256, 768]: self._request_stats(dp)
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
                
                if duration > 0:
                    speed_tx = (tx_bytes - prev_tx) / duration
                    speed_rx = (rx_bytes - prev_rx) / duration
                    
                    speed_tx_mbps = (speed_tx * 8) / 1000000.0
                    speed_rx_mbps = (speed_rx * 8) / 1000000.0
                    current_load_mbps = max(speed_tx_mbps, speed_rx_mbps)

                    port_limit = PORT_CAPACITY.get((dpid, port_no), DEFAULT_CAPACITY)

                    
                    if current_load_mbps > port_limit:
                        print(f"{Colors.RED}[!] CONGESTION ALERT: Switch {dpid} Port {port_no} "
                              f"| Load: {current_load_mbps:.2f} Mbps > Limit: {port_limit} Mbps{Colors.RESET}")
                        
                        if dpid == 256 and port_no == 1:
                            if not self.rerouted_flags.get('G1_Cloud'):
                                print(f"{Colors.YELLOW}>>> AUTO-ACTION: Rerouting Cloud Traffic via G3 (Port 5)...{Colors.RESET}")
                                self.change_route(256, "10.0.100.2", 5)
                                self.rerouted_flags['G1_Cloud'] = True
                                
                    elif current_load_mbps > 0.1:
                        print(f"   [INFO] SW {dpid} Port {port_no} | Load: {current_load_mbps:.2f} Mbps")
            
            self.prev_stats[key] = (rx_bytes, tx_bytes, time.time())

    def change_route(self, dpid, destination_ip, new_port):
        if dpid not in self.datapaths: return False
        datapath = self.datapaths[dpid]
        parser = datapath.ofproto_parser
        
        dst_mac = self.static_arp_table.get(destination_ip)
        if not dst_mac and ("10.0.100" in destination_ip or "10.0.200" in destination_ip): 
            dst_mac = self.CLOUD_MAC
        if not dst_mac: return False

        print(f"\n{Colors.YELLOW}--- [APPLYING NEW RULE] ---")
        print(f"Switch: {dpid} | Dest: {destination_ip} -> New Port: {new_port}{Colors.RESET}")

        
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=destination_ip)
        
        
        actions = [
            parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
            parser.OFPActionSetField(eth_dst=dst_mac), 
            parser.OFPActionOutput(new_port)
        ]
        
        
        self.add_flow(datapath, 100, match, actions)
        return True

    # --- BASIC FUNCTIONS ---
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
        dpid = datapath.id
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP: return
        
        # --- L2 LEARNING (Fix ping cung subnet) ---
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port
        
        
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocols(arp.arp)[0]
            if arp_pkt.opcode == arp.ARP_REQUEST:
                # Neu hoi Gateway -> Controller tra loi
                if arp_pkt.dst_ip in self.GW_IPS:
                    self.send_arp_reply(datapath, in_port, arp_pkt.src_mac, self.GATEWAY_MAC, arp_pkt.dst_ip, arp_pkt.src_ip)
                    return
                # Neu hoi Host khac -> Flood de tim
                else:
                    self.do_flood(datapath, msg, in_port)
                    return
            else: 
                # ARP Reply tu Host -> Flood de ve nguon
                self.do_flood(datapath, msg, in_port)
            return

        
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocols(ipv4.ipv4)[0]
            dst_ip = ip_pkt.dst
            
            # Neu dich la Gateway ao -> Drop (vi controller da tra loi ARP roi)
            if dst_ip in self.GW_IPS: return

            # --- L3 ROUTING (Dua vao bang dinh tuyen tinh) ---
            if dpid in self.routing_table:
                subnet_key = ".".join(dst_ip.split('.')[:3])
                routing_table = self.routing_table.get(dpid, {})
                out_port = routing_table.get(subnet_key)
                if not out_port: out_port = routing_table.get("default")
                
                # Chi Routing neu biet cong ra
                if out_port:
                   self.handle_ip_routing(datapath, in_port, ip_pkt, msg, out_port)
                   return

            # --- L2 SWITCHING (Fallback) ---
            # Neu khong co trong bang dinh tuyen (vi du cung subnet), dung MAC table
            if eth.dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][eth.dst]
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                match = datapath.ofproto_parser.OFPMatch(in_port=in_port, eth_dst=eth.dst)
                self.add_flow(datapath, 1, match, actions)
                
                data = msg.data if msg.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None
                out = datapath.ofproto_parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data)
                datapath.send_msg(out)
            else:
                self.do_flood(datapath, msg, in_port)

    def send_arp_reply(self, datapath, port, dst_mac, src_mac, src_ip, dst_ip):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP, dst=dst_mac, src=src_mac))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY, src_mac=src_mac, src_ip=src_ip, dst_mac=dst_mac, dst_ip=dst_ip))
        pkt.serialize()
        actions = [parser.OFPActionOutput(port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER, in_port=ofproto.OFPP_CONTROLLER, actions=actions, data=pkt.data)
        datapath.send_msg(out)

    def handle_ip_routing(self, datapath, in_port, ip_pkt, msg, out_port):
        dst_ip = ip_pkt.dst
        dst_mac = self.static_arp_table.get(dst_ip)
        if not dst_mac and ("10.0.100" in dst_ip or "10.0.200" in dst_ip): dst_mac = self.CLOUD_MAC

        if dst_mac:
            parser = datapath.ofproto_parser
            actions = [parser.OFPActionSetField(eth_src=self.GATEWAY_MAC),
                       parser.OFPActionSetField(eth_dst=dst_mac), 
                       parser.OFPActionOutput(out_port)]
            
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst_ip)
            # Priority thap (10) de de bi ghi de boi Auto-Reroute (100)
            self.add_flow(datapath, 10, match, actions)
            
            data = msg.data if msg.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)
        else:
            # Neu chua biet MAC dich -> Flood tam
            self.do_flood(datapath, msg, in_port)

    def do_flood(self, datapath, msg, in_port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

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