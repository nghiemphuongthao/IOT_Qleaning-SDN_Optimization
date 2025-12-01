import time, os, json, random
import numpy as np
from zmq_client import ZMQClient
from model import build_dqn
from replay import ReplayBuffer

# hyperparams
STATE_DIM = 10   # placeholder: adapt with encoding
ACTION_DIM = 4   # example: choose among 4 candidate paths
BUFFER_SIZE = 20000
BATCH = 32
GAMMA = 0.99
EPS = 1.0
EPS_MIN = 0.05
EPS_DECAY = 0.995

def encode_state(state):
    # encode to fixed vector: e.g., number of switches, average load, top-k loads...
    links = state.get("links", [])
    loads = [l.get("load",0) for l in links]
    loads_sorted = sorted(loads, reverse=True)[:8]
    vec = [len(state.get("switches",[]))] + loads_sorted
    while len(vec) < STATE_DIM:
        vec.append(0)
    return np.array(vec, dtype=np.float32)

def choose_action(model, s):
    if random.random() < EPS:
        return random.randint(0, ACTION_DIM-1)
    q = model.predict(s.reshape(1,-1), verbose=0)[0]
    return int(np.argmax(q))

def action_to_flow(action_idx, state):
    # Map action index to concrete path: here use fixed mapping as example
    # In practice generate k-shortest paths and map idx->path
    # Example pseudo path (source,dst) placeholders
    return {
        "type":"action",
        "agent_id":"agent-1",
        "flow":{
            "src_ip":"10.0.1.1",
            "dst_ip":"10.0.2.1",
            "path":[1,2,3],
            "priority":20,
            "timeout":30
        }
    }

def train_step(model, target, buffer):
    if len(buffer) < BATCH:
        return
    s,a,r,s2,d = buffer.sample(BATCH)
    q_next = target.predict(s2, verbose=0)
    q_target = model.predict(s, verbose=0)
    for i in range(BATCH):
        q_target[i, a[i]] = r[i] + (0 if d[i] else GAMMA * np.max(q_next[i]))
    model.train_on_batch(s, q_target)

def main():
    global EPS
    client = ZMQClient()
    model = build_dqn(STATE_DIM, ACTION_DIM)
    target = build_dqn(STATE_DIM, ACTION_DIM)
    target.set_weights(model.get_weights())
    buffer = ReplayBuffer(BUFFER_SIZE)
    step = 0
    while True:
        state = client.recv_state()  # blocking read
        s = encode_state(state)
        a = choose_action(model, s)
        # send action
        act_msg = action_to_flow(a, state)
        reply = client.send_action(act_msg)
        # compute reward (simple negative sum of load on chosen path)
        links = state.get("links", [])
        reward = -sum([l.get('load',0) for l in links]) / 1000.0
        # get next state (could wait or use immediate)
        time.sleep(0.5)
        state2 = client.recv_state()
        s2 = encode_state(state2)
        done = False
        buffer.add(s,a,reward,s2,done)
        train_step(model, target, buffer)
        if step % 50 == 0:
            target.set_weights(model.get_weights())
            # save weights
            model.save_weights('/shared/agent_weights.h5')
        EPS = max(EPS_MIN, EPS * EPS_DECAY)
        step += 1

if __name__ == '__main__':
    main()
