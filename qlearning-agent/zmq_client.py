import zmq

class ZmqClient:
    def __init__(self, pub_addr, req_addr):
        self.ctx = zmq.Context()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(pub_addr)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self.req = self.ctx.socket(zmq.REQ)
        self.req.connect(req_addr)

    def recv_metrics(self, timeout_ms=2000):
        poller = zmq.Poller()
        poller.register(self.sub, zmq.POLLIN)
        socks = dict(poller.poll(timeout_ms))
        if socks.get(self.sub) == zmq.POLLIN:
            return self.sub.recv_json()
        return None

    def send_action(self, payload):
        self.req.send_json(payload)
        return self.req.recv_json()

    def close(self):
        try:
            self.sub.close(0)
            self.req.close(0)
            self.ctx.term()
        except Exception:
            pass
