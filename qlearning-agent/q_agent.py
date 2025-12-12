import zmq
import random
import time

ctx = zmq.Context()

state_socket = ctx.socket(zmq.PULL)
state_socket.connect("tcp://ryu-controller:5556")

action_socket = ctx.socket(zmq.PUSH)
action_socket.connect("tcp://ryu-controller:5557")

print("Q-learning agent started")

while True:
    state = state_socket.recv_json()
    print("[AGENT] state:", state)

    action = {
        "dpid": state["dpid"],
        "dst": state["dst"],
        "out_port": random.choice([1, 2, 3])
    }

    action_socket.send_json(action)
    time.sleep(0.1)
