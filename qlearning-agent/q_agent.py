import time
import random
import requests
import pandas as pd
import os

# ================= CONFIG =================
RYU_HOST = os.environ.get("RYU_HOST", "ryu-controller")
RYU_PORT = 8080
RYU_API = f"http://{RYU_HOST}:{RYU_PORT}"

DPID = 256
DEST_SUBNET = "10.0.100"      # subnet, not host

ACTIONS = [1, 5]              # output ports (primary / backup)
ALPHA = 0.5                   # learning rate
GAMMA = 0.9                   # discount factor
EPSILON = 0.2                 # exploration rate

CSV_DIR = "/shared/raw"
INTERVAL = 10                 # seconds between decisions
FLOW_SETTLE_TIME = 3          # wait after policy update

# ================= Q-TABLE =================
Q = {
    "LOW":    [0.0, 0.0],
    "MEDIUM": [0.0, 0.0],
    "HIGH":   [0.0, 0.0]
}

# ================= METRIC READING =================
def read_throughput():
    """
    Read latest CLOUD (server) throughput.
    This represents real network performance.
    """
    try:
        files = [
            f for f in os.listdir(CSV_DIR)
            if f.endswith(".csv") and "server" in f
        ]
        if not files:
            return 0.0

        # Sort by modified time (newest last)
        files.sort(
            key=lambda f: os.path.getmtime(os.path.join(CSV_DIR, f))
        )

        df = pd.read_csv(os.path.join(CSV_DIR, files[-1]))

        if "throughput" not in df.columns or df.empty:
            return 0.0

        # Use latest measurement
        return float(df["throughput"].iloc[-1])

    except Exception as e:
        print(f"[AGENT] Metric read error: {e}", flush=True)
        return 0.0


# ================= STATE =================
def get_state(throughput):
    """
    Discretize throughput into performance states.
    Tuned for ~5 Mbps traffic.
    """
    if throughput < 2:
        return "LOW"
    elif throughput < 4:
        return "MEDIUM"
    else:
        return "HIGH"


# ================= ACTION SELECTION =================
def choose_action(state):
    """
    Epsilon-greedy policy.
    """
    if random.random() < EPSILON:
        return random.randint(0, 1)
    return Q[state].index(max(Q[state]))


# ================= SEND POLICY UPDATE =================
def wait_for_switch(dpid, timeout=20, interval=1):
    url = f"{RYU_API}/switches"
    start = time.time()

    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                switches = r.json()   # 👈 LIST
                if dpid in switches:
                    print(f"[AGENT] Switch {dpid} is ready", flush=True)
                    return True
        except Exception as e:
            print(f"[AGENT] wait switch error: {e}", flush=True)

        time.sleep(interval)

    print(f"[AGENT] Timeout waiting for switch {dpid}", flush=True)
    return False



def send_action(action_idx):
    """
    Notify Ryu controller to update forwarding policy.
    """
    port = ACTIONS[action_idx]
    url = f"{RYU_API}/router/{DPID}"

    # # 🔥 đợi switch connect trước
    # if not wait_for_switch(DPID):
    #     print("[AGENT] Switch not ready, skip action", flush=True)
    #     return

    payload = {
        "dest": DEST_SUBNET,
        "port": port
    }

    try:
        r = requests.post(url, json=payload, timeout=2)
        return r.status_code == 200
    except Exception as e:
        print(f"[AGENT] API error: {e}", flush=True)
        return False


# ================= MAIN LOOP =================
print("[AGENT] Q-learning agent started (CASE 3 – Performance Optimization)", flush=True)

while True:
    # --- Observe current performance ---
    throughput = read_throughput()
    state = get_state(throughput)

    # --- Select & apply action ---
    action = choose_action(state)
    ok = send_action(action)

    # --- Wait for data plane to reflect change ---
    time.sleep(FLOW_SETTLE_TIME)

    # --- Observe new performance ---
    next_throughput = read_throughput()
    next_state = get_state(next_throughput)

    # --- Reward = achieved throughput ---
    reward = next_throughput if ok else -5.0

    # --- Q-learning update ---
    Q[state][action] = Q[state][action] + ALPHA * (
        reward + GAMMA * max(Q[next_state]) - Q[state][action]
    )

    # --- Logging ---
    print(
        f"[AGENT] state={state:<6} "
        f"action=port{ACTIONS[action]} "
        f"reward={reward:5.2f} "
        f"Q={Q[state]}",
        flush=True
    )

    time.sleep(INTERVAL)
