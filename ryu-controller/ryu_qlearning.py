import json
import logging
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, ether_types
from ryu.lib import hub
from ryu.app.wsgi import ControllerBase, WSGIApplication, route

from ryu.ofproto import ofproto_v1_3 as ofp

from webob import Response
import time

# ================= CONFIG =================
MONITOR_INTERVAL = 2
CONGESTION_THRESHOLD = 4_000_000  # 4 MB/s

simple_switch_instance_name = 'simple_switch_api_app'
url = '/router/{dpid}'


# ================= CONTROLLER =================
class AntiLoopController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.info("[SYSTEM] L3 Q-Learning SDN Controller READY")

        wsgi = kwargs['wsgi']
        wsgi.register(
            RestRouterController,
            {simple_switch_instance_name: self}
        )

        self.datapaths = {}

        # ===== STATIC ROUTING TABLE =====
        self.routing_table = {
            256: {   # g1
                "10.0.1.0/24": 2,
                "10.0.2.0/24": 3,
                "10.0.3.0/24": 4,
                "10.0.4.0/24": 5,
                "10.0.100.0/24": 1
            },
            512: {   # g2
                "10.0.3.0/24": 2,
                "default": 1
            },
            768: {   # g3
                "10.0.4.0/24": 2,
                "10.0.100.0/24": 3,
                "default": 1
            }
        }

    # =======================
    # SWITCH CONNECT
    # =======================
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        self.datapaths[dp.id] = dp
        self.logger.info("[SWITCH] Connected dpid=%s", dp.id)

        # 1️⃣ TABLE-MISS → send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                        ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, priority=0, match=match, actions=actions)

        # 2️⃣ ARP FLOOD
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        self.add_flow(dp, priority=10, match=match, actions=actions)


    # =======================
    # PACKET IN (ARP HANDLING)
    # =======================
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        ip = pkt.get_protocol(ipv4.ipv4)
        if not ip:
            return

        dpid = dp.id
        dst = ip.dst

        # Lookup routing table
        port = self.routing_table.get(dpid, {}).get(dst)

        if not port:
            return

        actions = [parser.OFPActionOutput(port)]

        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=ofp.OFP_NO_BUFFER,
            in_port=msg.match['in_port'],
            actions=actions,
            data=msg.data
        )
        dp.send_msg(out)


    def _handle_arp(self, dp, pkt, in_port):
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt.opcode != arp.ARP_REQUEST:
            return

        # Proxy ARP cho gateway *.254
        if not arp_pkt.dst_ip.endswith(".254"):
            return

        self.logger.info(
            "[ARP] Reply %s is-at %s",
            arp_pkt.dst_ip, "aa:bb:cc:dd:ee:ff"
        )

        e = ethernet.ethernet(
            dst=arp_pkt.src_mac,
            src="aa:bb:cc:dd:ee:ff",
            ethertype=0x0806
        )
        a = arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac="aa:bb:cc:dd:ee:ff",
            src_ip=arp_pkt.dst_ip,
            dst_mac=arp_pkt.src_mac,
            dst_ip=arp_pkt.src_ip
        )

        p = packet.Packet()
        p.add_protocol(e)
        p.add_protocol(a)
        p.serialize()

        actions = [dp.ofproto_parser.OFPActionOutput(in_port)]
        out = dp.ofproto_parser.OFPPacketOut(
            datapath=dp,
            buffer_id=ofp.OFP_NO_BUFFER,
            in_port=ofp.OFPP_CONTROLLER,
            actions=actions,
            data=p.data
        )
        dp.send_msg(out)

    # =======================
    # L3 FLOW INSTALL
    # =======================
    def _install_l3_flow(self, dp, subnet, port):
        parser = dp.ofproto_parser

        if '/' not in subnet:
            subnet = subnet + '/24'   # normalize

        ip, mask = subnet.split('/')
        mask = int(mask)

        match = parser.OFPMatch(
            eth_type=0x0800,
            ipv4_dst=(ip, self._mask_to_netmask(mask))
        )

        actions = [
            parser.OFPActionDecNwTtl(),
            parser.OFPActionOutput(port)
        ]

        self._add_flow(dp, 10, match, actions)

        self.logger.info(
            "Installed flow dpid=%s subnet=%s → port %s",
            dp.id, subnet, port
        )

    # =======================
    # REST UPDATE ROUTE
    # =======================
    def change_route(self, dpid, dest, port):
        self.routing_table.setdefault(dpid, {})[dest] = port

        dp = self.datapaths.get(dpid)
        if not dp:
            self.logger.warning(
                "[ROUTE] datapath %s not connected yet", dpid
            )
            return False
        if '/' not in dest:
            dest = dest + '.0/24'   # normalize subnet
        self._install_l3_flow(dp, dest, port)
        return True

    # =======================
    # UTILS
    # =======================
    def _add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        inst = [
            parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            match=match,
            instructions=inst
        )
        dp.send_msg(mod)

    def _mask_to_netmask(self, mask):
        return ".".join(
            str((0xffffffff << (32 - mask) >> i) & 0xff)
            for i in [24, 16, 8, 0]
        )
# ================= REST API =================
class RestRouterController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(RestRouterController, self).__init__(req, link, data, **config)

        # 🔥 BẮT BUỘC
        self.app = data[simple_switch_instance_name]

        # Log khi controller được khởi tạo
        self.app.logger.info(
            "[REST][INIT] RestRouterController initialized"
        )

    @route('router', '/switches', methods=['GET'])
    def list_switches(self, req):
        return Response(
            content_type='application/json',
            body=json.dumps(list(self.app.datapaths.keys())).encode()
        )


    @route('router', url, methods=['POST'], requirements={'dpid': '[0-9]+'})
    def set_route(self, req, **kwargs):
        dpid = int(kwargs['dpid'])

        # ===== LOG REQUEST =====
        self.app.logger.info(
            "[REST][REQ] POST /router/%s", dpid
        )

        try:
            body = req.json if req.body else {}
            self.app.logger.info(
                "[REST][BODY] %s", body
            )

            dest = body.get("dest")
            port = body.get("port")

        except Exception as e:
            self.app.logger.exception(
                "[REST][ERROR] Invalid JSON: %s", str(e)
            )
            return Response(
                status=400,
                content_type="application/json",
                body=json.dumps({
                    "status": "error",
                    "reason": "invalid_json"
                }).encode()
            )

        if not dest or not port:
            self.app.logger.warning(
                "[REST][WARN] Missing dest or port: dest=%s port=%s",
                dest, port
            )
            return Response(
                status=400,
                content_type="application/json",
                body=json.dumps({
                    "status": "error",
                    "reason": "missing_dest_or_port"
                }).encode()
            )

        # ===== CALL APP LOGIC =====
        self.app.logger.info(
            "[REST][CALL] change_route(dpid=%s, dest=%s, port=%s)",
            dpid, dest, port
        )

        ok = self.app.change_route(dpid, dest, int(port))

        # ===== RESULT LOG =====
        if ok:
            self.app.logger.info(
                "[REST][OK] Route updated: dpid=%s dest=%s port=%s",
                dpid, dest, port
            )
            return Response(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "status": "ok",
                    "dpid": dpid,
                    "dest": dest,
                    "port": int(port)
                }).encode()
            )
        else:
            self.app.logger.error(
                "[REST][FAIL] change_route failed: dpid=%s dest=%s port=%s",
                dpid, dest, port
            )
            return Response(
                status=500,
                content_type="application/json",
                body=json.dumps({
                    "status": "error",
                    "reason": "flow_install_failed",
                    "dpid": dpid,
                    "dest": dest,
                    "port": int(port)
                }).encode()
            )
