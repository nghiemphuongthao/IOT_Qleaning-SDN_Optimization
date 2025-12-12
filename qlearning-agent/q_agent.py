import zmq
import time
import random
import pickle
import os
from collections import defaultdict

# =====================================================
# Q-learning hyperparameters
# =====================================================
ALPHA = 0.1        # learning rate
GAMMA = 0.9        # discount factor
EPSILON = 0.1      # exploration probability

# Output ports (adjust if topology changes)
ACTIONS = [1, 2, 3]

# Queue thresholds (bytes) for reward shaping
LOW_Q = 5_000
HIGH_Q = 20_000

# Q-table persistence
QTABLE_PATH = "/shared/qtable.pkl"

# =====================================================
# ZMQ setup
# =====================================================
ctx = zmq.Context.instance()

state_socket = ctx.socket(zmq.PULL)
state_socket.connect("tcp://ryu-controller:5556")

action_socket = ctx.socket(zmq.PUSH)
action_socket.connect("tcp://ryu-controller:5557")

# =====================================================
# Q-table initialization
# =====================================================
if os.path.exists(QTABLE_PATH):
    with open(QTABLE_PATH, "rb") as f:
        Q = pickle.load(f)
    print("[AGENT] Loaded Q-table from disk")
else:
    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
    print("[AGENT] Initialized new Q-table")

# =====================================================
# Helper functions
# =====================================================
def choose_action(state):
    """Epsilon-greedy action selection."""
    if random.random() < EPSILON:
        return random.choice(ACTIONS)
    return max(Q[state], key=Q[state].get)


def compute_reward(queue_len):
    """
    Reward based on queue backlog.
    Smaller queue -> higher reward.
    """
    if queue_len < LOW_Q:
        return 1.0
    elif queue_len < HIGH_Q:
        return 0.0
    else:
        return -1.0


def update_q(prev_state, action, reward, next_state):
    """Bellman Q-learning update."""
    best_next = max(Q[next_state].values())
    Q[prev_state][action] += ALPHA * (
        reward + GAMMA * best_next - Q[prev_state][action]
    )


def save_qtable():
    with open(QTABLE_PATH, "wb") as f:
        pickle.dump(Q, f)
    print("[AGENT] Q-table saved")


# =====================================================
# Main learning loop
# =====================================================
print("[AGENT] Q-learning agent started")

prev_state = None
prev_action = None

try:
    while True:
        # Receive state from controller
        state_msg = state_socket.recv_json()

        # Define state (minimal but meaningful)
        state = (state_msg["dpid"], state_msg["dst"])

        # Choose action
        action = choose_action(state)

        # Compute reward from queue length
        queue_len = state_msg.get("queue_len", 0)
        reward = compute_reward(queue_len)

        # Q-learning update
        if prev_state is not None:
            update_q(prev_state, prev_action, reward, state)

        # Send action back to controller
        action_socket.send_json({
            "dpid": state_msg["dpid"],
            "dst": state_msg["dst"],
            "out_port": action
        })

        prev_state = state
        prev_action = action

        # Periodic persistence
        if random.random() < 0.01:
            save_qtable()

        time.sleep(0.05)

except KeyboardInterrupt:
    print("[AGENT] Interrupted, saving Q-table...")
    save_qtable()
