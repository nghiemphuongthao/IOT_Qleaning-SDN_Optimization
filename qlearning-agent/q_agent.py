import os
import time
import signal
import json
import argparse
import csv
from datetime import datetime

import numpy as np

from model import QTable, encode_state, ACTIONS
from zmq_client import ZmqClient

# Config via env or defaults
QTABLE_PATH = os.environ.get("QTABLE_FILE", "/shared/qtable.npy")
LOG_CSV = os.environ.get("TRAIN_LOG", "/shared/training_log.csv")
PUB_ADDR = os.environ.get("ZMQ_PUB_ADDR", "tcp://ryu-controller:5556")
REQ_ADDR = os.environ.get("ZMQ_REQ_ADDR", "tcp://ryu-controller:5557")

EPS_START = float(os.environ.get("EPS_START", "0.5"))
EPS_END = float(os.environ.get("EPS_END", "0.05"))
EPS_DECAY = float(os.environ.get("EPS_DECAY", "0.9997"))
ALPHA = float(os.environ.get("ALPHA", "0.25"))
GAMMA = float(os.environ.get("GAMMA", "0.95"))

AUTOSAVE_INTERVAL = int(os.environ.get("AUTOSAVE_INTERVAL", "30"))  # seconds

class AgentApp:
    def __init__(self):
        self.qtable = QTable(path=QTABLE_PATH)
        self.epsilon = EPS_START
        self.alpha = ALPHA
        self.gamma = GAMMA
        self.running = True
        self.last_save = time.time()

        # ZMQ client
        self.zmq = ZmqClient(pub_addr=PUB_ADDR, req_addr=REQ_ADDR)

        # CSV logging
        self.log_path = LOG_CSV
        if not os.path.exists(os.path.dirname(self.log_path)):
            try:
                os.makedirs(os.path.dirname(self.log_path))
            except Exception:
                pass
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w") as f:
                w = csv.writer(f)
                w.writerow(["ts", "state_idx", "action_idx", "action", "reward", "epsilon"])

        # signal handlers
        signal.signal(signal.SIGINT, self._on_sig)
        signal.signal(signal.SIGTERM, self._on_sig)

    def _on_sig(self, signum, frame):
        print("Agent received signal, saving Q-table...")
        self.qtable.save()
        self.running = False

    def compute_reward(self, old_metrics, new_metrics):
        """
        Reward design (example):
        - penalize delay (ms), loss (%), energy (units)
        - reward larger when all are reduced.
        returns float reward.
        """
        # ensure keys exist
        d_old = old_metrics.get("delay", 0.0)
        l_old = old_metrics.get("loss", 0.0)
        e_old = old_metrics.get("energy", 0.0)

        d_new = new_metrics.get("delay", d_old)
        l_new = new_metrics.get("loss", l_old)
        e_new = new_metrics.get("energy", e_old)

        # normalize by expected max (tunable)
        rd = (d_old - d_new) / (1.0 + d_old)
        rl = (l_old - l_new) / (1.0 + l_old)
        re = (e_old - e_new) / (1.0 + e_old)

        # weighted sum (tune weights)
        reward = 1.0 * rd + 2.0 * rl + 0.8 * re
        # small scale
        return float(reward)

    def _choose_action(self, state_idx):
        if np.random.rand() < self.epsilon:
            return int(np.random.randint(0, len(ACTIONS)))
        return self.qtable.argmax(state_idx)

    def _build_action_payload(self, action_name, state_metrics):
        """
        Map action name to controller action payload.
        (Customize mapping to your topology)
        """
        if action_name == "INSTALL_METER":
            return {"type": "install_meter", "dpid": 1, "meter_id": 100, "rate_kbps": 10000}
        elif action_name == "PATH_G1":
            return {"type": "install_path", "dpid": 1, "src": "10.0.0.1", "dst": "10.0.0.254", "out_port": 1}
        elif action_name == "PATH_G2":
            return {"type": "install_path", "dpid": 1, "src": "10.0.0.1", "dst": "10.0.0.254", "out_port": 2}
        elif action_name == "PRIORITIZE_CRITICAL":
            return {"type": "set_queue", "info": "prioritize_critical"}
        else:
            return {"type": "raw", "cmd": "noop"}

    def _log(self, s_idx, a_idx, reward):
        with open(self.log_path, "a") as f:
            w = csv.writer(f)
            w.writerow([time.time(), s_idx, a_idx, ACTIONS[a_idx], reward, self.epsilon])

    def run(self):
        print("Agent running. Subscribing to controller at", PUB_ADDR)
        prev_metrics = {"delay": 0.0, "loss": 0.0, "energy": 0.0, "queue": 0.0}

        while self.running:
            msg = self.zmq.recv_metrics(timeout_ms=2000)
            if msg is None:
                # no metric -> periodic save
                if time.time() - self.last_save > AUTOSAVE_INTERVAL:
                    self.qtable.save()
                    self.last_save = time.time()
                continue

            # Parse possible message formats:
            # controller sends either port_metrics or metrics snapshot or packet_state
            metrics = {}
            if isinstance(msg, dict):
                if msg.get("type") == "port_metrics":
                    # convert port metric to aggregate metric sample
                    metrics["delay"] = 0.0
                    metrics["loss"] = msg.get("tx_errors", 0) + msg.get("tx_dropped", 0)
                    metrics["energy"] = msg.get("energy", 0.0)
                    metrics["queue"] = 0.0
                elif msg.get("type") == "packet_state":
                    metrics = msg.get("metrics", {})
                elif "avg_util_mbps" in msg:
                    metrics = {"delay": 0.0, "loss": 0.0, "energy": msg.get("total_energy", 0.0), "queue": 0.0}
                else:
                    # fallback: try keys
                    metrics = {
                        "delay": msg.get("delay", 0.0),
                        "loss": msg.get("loss", 0.0),
                        "energy": msg.get("energy", 0.0),
                        "queue": msg.get("queue", 0.0)
                    }
            else:
                # unknown format
                continue

            # encode state
            s_idx = encode_state(metrics)

            # choose action
            a_idx = self._choose_action(s_idx)
            action_name = ACTIONS[a_idx]

            # send action to controller
            payload = self._build_action_payload(action_name, metrics)
            resp = self.zmq.send_action(payload)

            # after action, query metrics for next state (controller supports query_metrics)
            next_req = {"type": "query_metrics"}
            next_resp = self.zmq.send_action(next_req)
            next_metrics = {}
            if isinstance(next_resp, dict) and next_resp.get("status") and next_resp.get("metrics"):
                next_metrics = next_resp["metrics"]
            else:
                # fallback to current metrics if no reply
                next_metrics = metrics

            # compute reward
            reward = self.compute_reward(prev_metrics, next_metrics)

            # Q update
            s2 = encode_state(next_metrics)
            # target = r + gamma * max_a' Q(s2,a')
            target = reward + self.gamma * self.qtable.best_value(s2)
            self.qtable.update(s_idx, a_idx, target, alpha=self.alpha)

            # log and decay epsilon
            self._log(s_idx, a_idx, reward)
            self.epsilon = max(EPS_END, self.epsilon * EPS_DECAY)

            prev_metrics = next_metrics

            # autosave
            if time.time() - self.last_save > AUTOSAVE_INTERVAL:
                self.qtable.save()
                self.last_save = time.time()

        # end run
        print("Agent shutting down; saving Q-table.")
        self.qtable.save()
        self.zmq.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Run agent in training mode (default behaviour)")
    args = parser.parse_args()

    app = AgentApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.qtable.save()
        print("Interrupted and saved.")

if __name__ == "__main__":
    main()