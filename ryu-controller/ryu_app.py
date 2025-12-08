import json
import time
import logging
from collections import defaultdict, deque

import zmq
import numpy as np

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, MAIN_DISPATCHER,
                                    set_ev_cls)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4

LOG = logging.getLogger('ryu.app.qos_energy_anomaly')
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
LOG.addHandler(handler)


class SDNQoS_Qlearning_Anomaly(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNQoS_Qlearning_Anomaly, self).__init__(*args, **kwargs)

        # --- state containers ---
        self.mac_to_port = defaultdict(dict)           # dpid -> {mac: port}
        self.flow_history = defaultdict(lambda: deque(maxlen=20))  # dpid -> deque(bytes)
        self.byte_rate = defaultdict(lambda: deque(maxlen=20))    # src_mac -> deque(tx_bytes)
        self.last_check = time.time()

        # --- ZMQ sockets: controller publishes state; agent subscribes. Agent sends action via REQ to REP ---
        ctx = zmq.Context()
        # PUB: publish states/metrics to agent (agent SUB)
        self.pub = ctx.socket(zmq.PUB)
        # bind to all interfaces inside container; compose exposes ports if needed
        self.pub.bind("tcp://*:5556")
        LOG.info("ZMQ PUB bound to tcp://*:5556")

        # REP: receive REQ from agent (agent REQ -> controller REP)
        self.rep = ctx.socket(zmq.REP)
        self.rep.bind("tcp://*:5557")
        LOG.info("ZMQ REP bound to tcp://*:5557")

        # small grace so SUB sockets can connect (optional)
        # note: avoid sleep in production; 0.2s allows subscribers to connect on start
        time.sleep(0.2)

        LOG.info("[+] Ryu-QoS-Qlearning-Anomaly initialized")

    # -----------------------
    # Switch features -> install table-miss (send to controller)
    # -----------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # Table-miss -> send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, priority=0, match=match, actions=actions)

        # ARP flood (allow ARP)
        match_arp = parser.OFPMatch(eth_type=0x0806)
        actions_arp = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        self.add_flow(dp, priority=100, match=match_arp, actions=actions_arp)

        LOG.info("Switch %s connected and base rules installed", dp.id)

    # -----------------------
    # Add flow helper
    # -----------------------
    def add_flow(self, dp, priority, match, actions, idle_timeout=0, hard_timeout=0, buffer_id=None):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=dp, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst,
                                    idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=dp, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        dp.send_msg(mod)
        LOG.debug("Flow add on dp=%s pr=%s match=%s", dp.id, priority, match)

    # -----------------------
    # Packet-in handler
    # -----------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        try:
            msg = ev.msg
            dp = msg.datapath
            parser = dp.ofproto_parser
            ofp = dp.ofproto
            in_port = msg.match.get('in_port', None)

            if in_port is None:
                LOG.debug("packet_in without in_port")
                return

            pkt = packet.Packet(msg.data)
            eth = pkt.get_protocol(ethernet.ethernet)
            if eth is None:
                return

            # ignore LLDP/mgmt ethertype if any
            if eth.ethertype == 35020:
                return

            src = eth.src
            dst = eth.dst
            dpid = dp.id

            # Learn MAC -> port
            self.mac_to_port[dpid][src] = in_port

            # Determine out_port
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
            else:
                out_port = ofp.OFPP_FLOOD

            # Build a compact state for the agent
            state = self.collect_state_features(dpid, src)

            # Publish state so agent (SUB) sees it
            metrics = self._metrics_snapshot()
            state_msg = {"type": "packet_state", "dpid": dpid, "src": src, "dst": dst, "metrics": metrics, "ts": time.time()}
            try:
                # publish as string JSON
                self.pub.send_string(json.dumps(state_msg))
                LOG.debug("Published state to ZMQ: %s", state_msg)
            except Exception:
                LOG.exception("ZMQ publish failed")

            # Poll REP socket briefly to see if agent sent an action
            action = self.query_qlearning(timeout_ms=250)  # wait up to 250ms for agent REQ
            LOG.debug("Selected action: %s", action)

            # Map action to OpenFlow actions (queues/metering)
            actions = self.map_action_to_qos(parser, df=action, out_port=out_port)

            # Install flow to reduce future packet_in events (if not flooding)
            if out_port != ofp.OFPP_FLOOD:
                match = parser.OFPMatch(eth_src=src, eth_dst=dst)
                self.add_flow(dp, priority=10, match=match, actions=actions, idle_timeout=30)

            # Send PacketOut
            out = parser.OFPPacketOut(datapath=dp, buffer_id=ofp.OFP_NO_BUFFER,
                                      in_port=in_port, actions=actions, data=msg.data)
            dp.send_msg(out)

        except Exception:
            LOG.exception("Exception in packet_in_handler")

    # -----------------------
    # Collect state features for agent (simple)
    # -----------------------
    def collect_state_features(self, dpid, src_mac):
        # safe access to byte_rate
        try:
            brate = np.mean(self.byte_rate[src_mac]) if len(self.byte_rate[src_mac]) else 0.0
        except Exception:
            brate = 0.0
        entropy = self.compute_entropy(dpid)
        return {"byte_rate": float(brate), "entropy": float(entropy)}

    # -----------------------
    # Simple entropy-based anomaly detector
    # -----------------------
    def compute_entropy(self, dpid):
        flows = self.flow_history[dpid]
        if not flows:
            return 0.0
        arr = np.array(flows, dtype=float)
        s = arr.sum()
        if s <= 0:
            return 0.0
        arr = arr / (s + 1e-9)
        entropy = - (arr * np.log2(arr + 1e-9)).sum()
        return float(entropy)

    # -----------------------
    # Small metrics snapshot aggregator
    # -----------------------
    def _metrics_snapshot(self):
        vals = []
        for v in self.byte_rate.values():
            if len(v):
                vals.append(float(v[-1]))
        avg = float(np.mean(vals)) if vals else 0.0
        return {"avg_byte_rate": round(avg, 3), "ports": len(vals)}

    # -----------------------
    # Poll REP socket for agent action (non-blocking with timeout)
    # Agent is expected to SEND a REQ with {"type":"action","action": <int>}
    # Controller replies with ack {"status":"ok"}.
    # -----------------------
    def query_qlearning(self, timeout_ms=200):
        try:
            poller = zmq.Poller()
            poller.register(self.rep, zmq.POLLIN)
            socks = dict(poller.poll(timeout_ms))
            if self.rep in socks and socks[self.rep] == zmq.POLLIN:
                req = self.rep.recv_json()
                action = int(req.get("action", 0))
                # send ack/reply
                self.rep.send_json({"status": "ok"})
                LOG.debug("Received action from agent: %s", action)
                return action
            else:
                return 0
        except Exception:
            LOG.exception("query_qlearning error")
            # attempt to recover by returning default action
            try:
                # If REP is in a bad state we ignore and continue
                return 0
            except Exception:
                return 0

    # -----------------------
    # Map numeric action -> OpenFlow actions (queue assignment / output)
    # -----------------------
    def map_action_to_qos(self, parser, df, out_port):
        ofp = ofproto_v1_3
        # default: simple output
        if df == 1:
            # High priority: set queue 1 then output
            return [parser.OFPActionSetQueue(1), parser.OFPActionOutput(out_port)]
        if df == 2:
            return [parser.OFPActionSetQueue(2), parser.OFPActionOutput(out_port)]
        if df == 3:
            # policing would be done via meters; here we just use queue 3
            return [parser.OFPActionSetQueue(3), parser.OFPActionOutput(out_port)]
        if df == 4:
            # isolate/anomaly
            return [parser.OFPActionSetQueue(4), parser.OFPActionOutput(out_port)]
        # fallback
        return [parser.OFPActionOutput(out_port)]