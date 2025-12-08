import zmq
import json
import time

class ZmqClient:
    def __init__(self, pub_addr="tcp://ryu-controller:5556", req_addr="tcp://ryu-controller:5557", sub_topic=""):
        self.ctx = zmq.Context()
        # SUB socket (controller PUB -> agent SUB)
        self.sub = self.ctx.socket(zmq.SUB)
        # connect to controller's PUB
        self.sub.connect(pub_addr)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, sub_topic)

        # REQ socket (agent REQ -> controller REP)
        self.req = self.ctx.socket(zmq.REQ)
        self.req.connect(req_addr)
        # small linger to avoid hang on close
        self.req.linger = 1000

    def recv_metrics(self, timeout_ms=2000):
        """Try to recv one message as JSON. Returns dict or None."""
        poller = zmq.Poller()
        poller.register(self.sub, zmq.POLLIN)
        socks = dict(poller.poll(timeout_ms))
        if self.sub in socks and socks[self.sub] == zmq.POLLIN:
            raw = self.sub.recv_string()
            try:
                return json.loads(raw)
            except Exception:
                return {"raw": raw}
        return None

    def send_action(self, action_obj, timeout_ms=5000):
        """
        action_obj: JSON-serializable object describing action for controller.
        send and wait for reply (blocking).
        returns parsed JSON reply or raw string on error.
        """
        try:
            self.req.send_string(json.dumps(action_obj))
            # wait for reply (blocking)
            rep = self.req.recv_string()
            try:
                return json.loads(rep)
            except Exception:
                return {"raw_reply": rep}
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        try:
            self.sub.close()
            self.req.close()
            self.ctx.term()
        except Exception:
            pass