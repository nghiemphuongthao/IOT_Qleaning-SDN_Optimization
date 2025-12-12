import time
import zmq

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet


class QLearningSDNController(app_manager.RyuApp):
    """
    Learning-based SDN controller using Q-learning agent.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}

        # ZMQ sockets
        ctx = zmq.Context.instance()
        self.state_socket = ctx.socket(zmq.PUSH)
        self.state_socket.bind("tcp://*:5556")

        self.action_socket = ctx.socket(zmq.PULL)
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
        parser = dp.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == 0x88cc:
            return

        # Send state to agent
        state = {
            "dpid": dp.id,
            "src": eth.src,
            "dst": eth.dst,
            "in_port": msg.match['in_port'],
            "time": time.time()
        }
        self.state_socket.send_json(state)

        # Fallback: wait for agent decision
        # (temporary flooding)
        actions = [parser.OFPActionOutput(dp.ofproto.OFPP_FLOOD)]
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=msg.match['in_port'],
            actions=actions,
            data=msg.data
        ))

    def _listen_action(self):
        while True:
            action = self.action_socket.recv_json()
            self._apply_action(action)

    def _apply_action(self, action):
        dp = self.datapaths.get(action["dpid"])
        if not dp:
            return

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        actions = [parser.OFPActionOutput(action["out_port"])]
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=10,
            match=parser.OFPMatch(eth_dst=action["dst"]),
            instructions=[
                parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, actions
                )
            ]
        ))
