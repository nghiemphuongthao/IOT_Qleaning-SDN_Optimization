import os
import time
import json
import zmq
import networkx as nx
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology import event
from ryu.topology.api import get_link, get_switch
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

ZMQ_PUB_PORT = int(os.environ.get("ZMQ_PUB_PORT", 5556))
ZMQ_REP_PORT = int(os.environ.get("ZMQ_REP_PORT", 5557))

class RyuZMQ(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RyuZMQ, self).__init__(*args, **kwargs)

        self.net = nx.DiGraph()
        self.mac_table = {}
        self.port_stats = {}
        self.port_speed = {}
        self.datapaths = {}

        # ZeroMQ
        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.PUB)
        self.pub.bind(f"tcp://0.0.0.0:{ZMQ_PUB_PORT}")

        self.rep = self.context.socket(zmq.REP)
        self.rep.bind(f"tcp://0.0.0.0:{ZMQ_REP_PORT}")

        hub.spawn(self.rep_loop)
        hub.spawn(self.publisher)
        hub.spawn(self.monitor_stats)

        self.logger.info("RyuZMQ loaded (PUB=%s, REP=%s)", ZMQ_PUB_PORT, ZMQ_REP_PORT)

    # ----------------------------
    # Topology
    # ----------------------------
    @set_ev_cls(event.EventSwitchEnter)
    def handler_topology(self, ev):
        switches = get_switch(self, None)
        links = get_link(self, None)

        self.net.clear()
        for sw in switches:
            self.net.add_node(sw.dp.id)

        for l in links:
            s1, p1 = l.src.dpid, l.src.port_no
            s2, p2 = l.dst.dpid, l.dst.port_no

            self.net.add_edge(s1, s2, port=p1, load=0)
            self.net.add_edge(s2, s1, port=p2, load=0)

        self.logger.info("Topo updated: %s", list(self.net.edges()))

    # ----------------------------
    # Switch Features
    # ----------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            match=match,
            priority=0,
            instructions=inst
        ))

        self.datapaths[dp.id] = dp
        self.logger.info("Registered datapath %s", dp.id)

    # ----------------------------
    # Packet In
    # ----------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        dpid = dp.id

        in_port = msg.match['in_port']

        from ryu.lib.packet import packet, ethernet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == 0x88cc:
            return

        src = eth.src
        dst = eth.dst

        self.mac_table.setdefault(dpid, {})
        self.mac_table[dpid][src] = in_port

        dst_sw = None
        for sw, table in self.mac_table.items():
            if dst in table:
                dst_sw = sw
                break

        if dst_sw is None:
            out_port = ofp.OFPP_FLOOD
        else:
            if dpid == dst_sw:
                out_port = self.mac_table[dpid][dst]
            else:
                try:
                    path = nx.shortest_path(self.net, dpid, dst_sw, weight="load")
                    next_hop = path[1]
                    out_port = self.net[dpid][next_hop]['port']
                except:
                    out_port = ofp.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            match=parser.OFPMatch(eth_dst=dst),
            priority=1,
            instructions=[
                parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)
            ]
        ))

        data = None if msg.buffer_id != ofp.OFP_NO_BUFFER else msg.data
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        ))

    # ----------------------------
    # Stats monitor
    # ----------------------------
    def monitor_stats(self):
        while True:
            for dp in list(self.datapaths.values()):
                parser = dp.ofproto_parser
                req = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req)
            hub.sleep(1)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats(self, ev):
        dp = ev.msg.datapath
        dpid = dp.id
        body = ev.msg.body

        self.port_stats.setdefault(dpid, {})
        self.port_speed.setdefault(dpid, {})

        for stat in body:
            port_no = stat.port_no
            tx = stat.tx_bytes

            prev = self.port_stats[dpid].get(port_no, tx)
            speed = max(tx - prev, 0)

            self.port_stats[dpid][port_no] = tx
            self.port_speed[dpid][port_no] = speed

        for u, v in self.net.edges():
            p = self.net[u][v]['port']
            self.net[u][v]['load'] = self.port_speed.get(u, {}).get(p, 0)

    # ----------------------------
    # ZMQ REP – receive actions
    # ----------------------------
    def rep_loop(self):
        poller = zmq.Poller()
        poller.register(self.rep, zmq.POLLIN)

        while True:
            events = dict(poller.poll(timeout=100))
            if self.rep in events:
                try:
                    msg = self.rep.recv_json()
                    if msg.get("type") == "action":
                        ok, info = self.install_action(msg["flow"])
                        self.rep.send_json({"status": ok, "msg": info})
                    else:
                        self.rep.send_json({"status": False, "msg": "unknown"})
                except:
                    self.rep.send_json({"status": False, "msg": "error"})
            hub.sleep(0.01)

    # ----------------------------
    # Install flow from ML action
    # ----------------------------
    def install_action(self, flow):
        try:
            path = flow["path"]
            src_ip = flow["src_ip"]
            dst_ip = flow["dst_ip"]
            priority = flow.get("priority", 10)

            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                if not self.net.has_edge(u, v):
                    continue

                port = self.net[u][v]["port"]

                dp = self.datapaths.get(u)
                if not dp:
                    continue

                parser = dp.ofproto_parser
                ofp = dp.ofproto

                match = parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_src=src_ip,
                    ipv4_dst=dst_ip
                )
                actions = [parser.OFPActionOutput(port)]

                dp.send_msg(parser.OFPFlowMod(
                    datapath=dp,
                    priority=priority,
                    match=match,
                    instructions=[
                        parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)
                    ],
                    hard_timeout=60
                ))

            return True, "Flow installed"
        except Exception as e:
            return False, str(e)

    # ----------------------------
    # Publisher – send state to Agent
    # ----------------------------
    def publisher(self):
        while True:
            state = {
                "type": "state",
                "timestamp": time.time(),
                "switches": list(self.net.nodes()),
                "links": [
                    dict(u=u, v=v, port=self.net[u][v]["port"], load=self.net[u][v]["load"])
                    for u, v in self.net.edges()
                ],
                "mac_table": self.mac_table
            }
            try:
                self.pub.send_json(state, flags=zmq.NOBLOCK)
            except:
                pass
            hub.sleep(1)
