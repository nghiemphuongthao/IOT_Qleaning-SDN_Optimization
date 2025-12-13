from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, ether_types
from ryu.lib import hub
from ryu.topology.api import get_switch, get_link
import networkx as nx


class SmartController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SmartController, self).__init__(*args, **kwargs)

        self.topology_api_app = self
        self.net = nx.DiGraph()          # CHỈ switch
        self.datapaths = {}
        self.arp_table = {}              # ip -> mac
        self.hosts = {}                  # ip -> (dpid, port, mac)   <-- THÊM

        hub.spawn(self.topology_discovery)

    # ================= SWITCH FEATURES =================
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(f"[INIT] Switch {datapath.id} connected")

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
            mod = parser.OFPFlowMod(datapath=datapath,
                                    priority=priority,
                                    match=match,
                                    instructions=inst)
        datapath.send_msg(mod)

    # ================= TOPOLOGY =================
    def topology_discovery(self):
        while True:
            try:
                switch_list = get_switch(self.topology_api_app, None)
                for sw in switch_list:
                    self.net.add_node(sw.dp.id)

                link_list = get_link(self.topology_api_app, None)
                for link in link_list:
                    self.net.add_edge(
                        link.src.dpid,
                        link.dst.dpid,
                        port=link.src.port_no
                    )
            except:
                pass
            hub.sleep(2)

    # ================= PACKET IN =================
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        dpid = datapath.id
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # ================= ARP =================
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocol(arp.arp)

            # FIX: KHÔNG add host vào graph
            self.arp_table[arp_pkt.src_ip] = arp_pkt.src_mac
            self.hosts[arp_pkt.src_ip] = (dpid, in_port, arp_pkt.src_mac)

            if arp_pkt.opcode == arp.ARP_REQUEST:
                if arp_pkt.dst_ip in self.arp_table:
                    self.send_arp_reply(
                        datapath,
                        in_port,
                        arp_pkt.src_mac,
                        arp_pkt.dst_ip,
                        self.arp_table[arp_pkt.dst_ip],
                        arp_pkt.src_ip
                    )
                    return

            self.flood(msg)
            return

        # ================= IP ROUTING =================
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            dst_ip = ip_pkt.dst

            # FIX: route theo IP, không theo MAC
            if dst_ip not in self.hosts:
                self.flood(msg)
                return

            dst_dpid, dst_port, dst_mac = self.hosts[dst_ip]

            try:
                path = nx.shortest_path(self.net, dpid, dst_dpid)
                self.logger.info(f"[PATH] Found path: {path}")

                if dpid == dst_dpid:
                    out_port = dst_port
                else:
                    next_hop = path[1]
                    out_port = self.net[dpid][next_hop]['port']

                actions = [parser.OFPActionOutput(out_port)]

                # FIX: match L3
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP,
                    ipv4_dst=dst_ip
                )

                self.add_flow(datapath, 10, match, actions)

                data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
                out = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=msg.buffer_id,
                    in_port=in_port,
                    actions=actions,
                    data=data
                )
                datapath.send_msg(out)
                return

            except Exception as e:
                self.logger.info(f"[ERROR] Path failed: {e}")
                self.flood(msg)

    # ================= FLOOD =================
    def flood(self, msg):
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match['in_port'],
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ================= ARP REPLY =================
    def send_arp_reply(self, datapath, port, eth_dst, ip_src, mac_src, ip_dst):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_ARP,
            dst=eth_dst,
            src=mac_src
        ))
        pkt.add_protocol(arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac=mac_src,
            src_ip=ip_src,
            dst_mac=eth_dst,
            dst_ip=ip_dst
        ))
        pkt.serialize()

        actions = [parser.OFPActionOutput(port)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=pkt.data
        )
        datapath.send_msg(out)
