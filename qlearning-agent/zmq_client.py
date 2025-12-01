import zmq, os, time, json
ZMQ_PUB_ADDR = os.getenv('ZMQ_PUB_ADDR', 'tcp://ryu-controller:5556')
ZMQ_REQ_ADDR = os.getenv('ZMQ_REQ_ADDR', 'tcp://ryu-controller:5557')

class ZMQClient:
    def __init__(self):
        self.ctx = zmq.Context()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect(ZMQ_PUB_ADDR)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self.req = self.ctx.socket(zmq.REQ)
        self.req.connect(ZMQ_REQ_ADDR)

    def recv_state(self):
        msg = self.sub.recv_json()
        return msg

    def send_action(self, action):
        self.req.send_json(action)
        reply = self.req.recv_json()
        return reply
