from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
from ryu.lib.packet import packet, ethernet
import networkx as nx
import os
import time


class SDNRouter(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'switches': switches.Switches}
    MODE = os.environ.get("MODE", "baseline")

    if MODE == "baseline":
        print("[RYU] Disabled in baseline mode")
        while True:
            time.sleep(1000)

    def __init__(self, *args, **kwargs):
        super(SDNRouter, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.net = nx.DiGraph()
        self.topo_ready = False


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install table miss entry"""
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        action = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                         ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, action)]

        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath, priority=0,
            match=match, instructions=inst
        ))


    @set_ev_cls(event.EventSwitchEnter)
    def topo_discover(self, ev):
        """Discover topology when switch join"""
        switches = get_switch(self, None)
        links = get_link(self, None)

        self.net.clear()

        for s in switches:
            self.net.add_node(s.dp.id)

        for l in links:
            src = l.src
            dst = l.dst
            self.net.add_edge(src.dpid, dst.dpid, port=src.port_no)
            self.net.add_edge(dst.dpid, src.dpid, port=dst.port_no)

        self.logger.info("Topology updated:")
        self.logger.info(f"Nodes: {self.net.nodes()}")
        self.logger.info(f"Links: {self.net.edges()}")

        self.topo_ready = True


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Handle packet and compute path if needed"""
        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto
        dpid = dp.id
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == 0x88cc:  # Ignore LLDP
            return

        src = eth.src
        dst = eth.dst

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # If we know destination location → compute path
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            # Destination in another switch?
            location = None
            for sw in self.mac_to_port:
                if dst in self.mac_to_port[sw]:
                    location = sw
                    break

            if location is None:
                out_port = ofproto.OFPP_FLOOD
            else:
                if not self.topo_ready:
                    out_port = ofproto.OFPP_FLOOD
                else:
                    # Compute shortest path between dp and destination-switch
                    path = nx.shortest_path(self.net, dpid, location)
                    next_hop = path[1]
                    out_port = self.net[dpid][next_hop]['port']
                    self.logger.info(f"Path {src} → {dst} = {path}")

        # Install flow for fast path
        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp, priority=1,
            match=match,
            instructions=[parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )]
        ))

        # Forward packet
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        ))
