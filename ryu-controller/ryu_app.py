import os
import time
import json
import zmq

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet

CASE = os.getenv("CASE", "1")
USE_AGENT = (CASE == "2")

class IoTQoSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}

        # ZMQ
        self.ctx = zmq.Context()
        if USE_AGENT:
            self.state_socket = self.ctx.socket(zmq.PUSH)
            self.state_socket.bind("tcp://*:5556")

            self.action_socket = self.ctx.socket(zmq.PULL)
            self.action_socket.bind("tcp://*:5557")

            hub.spawn(self._listen_action)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, MAIN_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp

        ofp = dp.ofproto
        parser = dp.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=0,
            match=match,
            instructions=inst
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == 0x88cc:
            return

        # CASE 1: rule-based
        if CASE == "1":
            out_port = ofp.OFPP_FLOOD

        # CASE 2: send state to agent
        elif CASE == "2":
            state = {
                "dpid": dp.id,
                "src": eth.src,
                "dst": eth.dst,
                "in_port": in_port,
                "time": time.time()
            }
            self.state_socket.send_json(state)
            out_port = ofp.OFPP_FLOOD  # fallback

        else:
            return

        actions = [parser.OFPActionOutput(out_port)]
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=1,
            match=parser.OFPMatch(
                eth_dst=eth.dst
            ),
            instructions=[
                parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, actions
                )
            ]
        ))

    def _listen_action(self):
        while True:
            action = self.action_socket.recv_json()
            self._apply_action(action)

    def _apply_action(self, action):
        dp = self.datapaths.get(action["dpid"])
        if not dp:
            return

        ofp = dp.ofproto
        parser = dp.ofproto_parser

        match = parser.OFPMatch(eth_dst=action["dst"])
        actions = [parser.OFPActionOutput(action["out_port"])]

        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=10,
            match=match,
            instructions=[
                parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, actions
                )
            ]
        ))
