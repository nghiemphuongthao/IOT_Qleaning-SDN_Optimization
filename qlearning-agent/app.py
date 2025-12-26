import os
import json
import time
import threading
from dataclasses import dataclass
import csv
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request


class QoSModel:
    def __init__(self, congestion_threshold: float):
        self.th = float(congestion_threshold)

    def get_state(self, load_bps: float, drops: int) -> int:
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0
        try:
            d = int(drops)
        except Exception:
            d = 0
        if d > 0:
            return 2
        if load < 0.5 * self.th:
            return 0
        if load < 1.0 * self.th:
            return 1
        return 2

    def get_reward(self, load_bps: float, drops: int) -> float:
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0
        try:
            d = int(drops)
        except Exception:
            d = 0

        if d > 0:
            return -50.0
        if load < 0.5 * self.th:
            return 20.0
        if load < 1.0 * self.th:
            return 10.0
        return -5.0


class QAgent:
    def __init__(
        self,
        lr: float = 0.1,
        gamma: float = 0.9,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
    ):
        self.lr = float(lr)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_min = float(epsilon_min)
        self.epsilon_decay = float(epsilon_decay)

        self._lock = threading.Lock()

        self._q_tables = {}
        self._actions = {}
        self._last = {}
        self._step = 0

    def _ensure_key(self, key: str, action_ports):
        ports = [int(p) for p in action_ports]
        if key not in self._q_tables:
            self._q_tables[key] = np.zeros((3, len(ports)), dtype=np.float64)
            self._actions[key] = ports
            self._last[key] = None
            return

        if self._actions[key] != ports:
            old_ports = self._actions[key]
            old_q = self._q_tables[key]
            new_q = np.zeros((3, len(ports)), dtype=np.float64)
            for new_i, p in enumerate(ports):
                if p in old_ports:
                    old_i = old_ports.index(p)
                    new_q[:, new_i] = old_q[:, old_i]
            self._q_tables[key] = new_q
            self._actions[key] = ports
            self._last[key] = None

    def choose_action(self, key: str, state: int) -> int:
        if np.random.random() < self.epsilon:
            return int(np.random.randint(0, self._q_tables[key].shape[1]))
        return int(np.argmax(self._q_tables[key][state]))

    def learn(self, key: str, s: int, a: int, r: float, s_next: int):
        predict = self._q_tables[key][s][a]
        target = float(r) + self.gamma * float(np.max(self._q_tables[key][s_next]))
        self._q_tables[key][s][a] = predict + self.lr * (target - predict)

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay


@dataclass(frozen=True)
class ObservationKey:
    dpid: int
    port: int
    qid: int | None


class StateStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = {}

    def update(self, key: ObservationKey, load_bps: float, drops: int):
        with self._lock:
            self._metrics[key] = {
                "ts": time.time(),
                "load_bps": float(load_bps),
                "drops": int(drops),
            }

    def switch_snapshot(self, dpid: int):
        with self._lock:
            items = [
                (k, v)
                for k, v in self._metrics.items()
                if k.dpid == int(dpid)
            ]
        return items


THRESHOLD_BPS = float(os.environ.get("CONGESTION_THRESHOLD_BPS", "200000"))
MODEL = QoSModel(congestion_threshold=THRESHOLD_BPS)
AGENT = QAgent(
    lr=float(os.environ.get("QL_LR", "0.1")),
    gamma=float(os.environ.get("QL_GAMMA", "0.9")),
    epsilon=float(os.environ.get("QL_EPSILON", "1.0")),
    epsilon_min=float(os.environ.get("QL_EPSILON_MIN", "0.05")),
    epsilon_decay=float(os.environ.get("QL_EPSILON_DECAY", "0.995")),
)
STORE = StateStore()

LOG_PATH = Path(os.environ.get("QL_LOG_PATH", "/shared/raw/qlearning_agent_log.csv"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_log_lock = threading.Lock()
_log_initialized = False

app = Flask(__name__)


def _flow_key(dpid: int, dst_prefix: str) -> str:
    return f"{int(dpid)}:{dst_prefix}"


def _compute_switch_state(dpid: int) -> tuple[int, float, int]:
    snap = STORE.switch_snapshot(dpid)
    if not snap:
        return 0, 0.0, 0

    max_load = 0.0
    total_drops = 0
    for _, v in snap:
        max_load = max(max_load, float(v.get("load_bps", 0.0)))
        total_drops += int(v.get("drops", 0))

    state = MODEL.get_state(load_bps=max_load, drops=total_drops)
    return state, max_load, total_drops


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/observe")
def observe():
    body = request.get_json(force=True, silent=True) or {}
    dpid = int(body.get("dpid"))
    port = int(body.get("port"))
    qid = body.get("qid")
    qid = None if qid is None else int(qid)
    load_bps = float(body.get("load_bps", 0.0))
    drops = int(body.get("drops", 0))

    STORE.update(ObservationKey(dpid=dpid, port=port, qid=qid), load_bps=load_bps, drops=drops)
    state, max_load, total_drops = _compute_switch_state(dpid)
    return jsonify({"state": state, "max_load_bps": max_load, "total_drops": total_drops})


@app.post("/act")
def act():
    body = request.get_json(force=True, silent=True) or {}
    dpid = int(body.get("dpid"))
    dst_prefix = str(body.get("dst_prefix"))
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return jsonify({"error": "candidates required"}), 400

    state, max_load, total_drops = _compute_switch_state(dpid)
    key = _flow_key(dpid, dst_prefix)

    reward = None

    with AGENT._lock:
        AGENT._ensure_key(key, candidates)
        action_idx = AGENT.choose_action(key, state)
        out_port = int(AGENT._actions[key][action_idx])

        prev = AGENT._last.get(key)
        if prev is not None:
            s_prev, a_prev = prev
            r = MODEL.get_reward(load_bps=max_load, drops=total_drops)
            reward = float(r)
            AGENT.learn(key, s=s_prev, a=a_prev, r=r, s_next=state)

        AGENT._last[key] = (state, action_idx)
        AGENT._step += 1
        step = AGENT._step

        q_snapshot = None
        try:
            q_snapshot = AGENT._q_tables[key][state].tolist()
        except Exception:
            q_snapshot = None

        eps = float(AGENT.epsilon)

    global _log_initialized
    try:
        with _log_lock:
            if not _log_initialized or not LOG_PATH.exists():
                with LOG_PATH.open("a", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(
                        [
                            "ts",
                            "step",
                            "dpid",
                            "dst_prefix",
                            "state",
                            "action",
                            "out_port",
                            "epsilon",
                            "max_load_bps",
                            "total_drops",
                            "reward",
                            "q_values",
                        ]
                    )
                _log_initialized = True

            with LOG_PATH.open("a", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        float(time.time()),
                        int(step),
                        int(dpid),
                        str(dst_prefix),
                        int(state),
                        int(action_idx),
                        int(out_port),
                        float(eps),
                        float(max_load),
                        int(total_drops),
                        ("" if reward is None else float(reward)),
                        ("" if q_snapshot is None else json.dumps(q_snapshot)),
                    ]
                )
    except Exception:
        pass

    return jsonify(
        {
            "dpid": dpid,
            "dst_prefix": dst_prefix,
            "state": state,
            "action": action_idx,
            "out_port": out_port,
            "epsilon": float(eps),
            "step": step,
        }
    )


@app.get("/debug/summary")
def debug_summary():
    with AGENT._lock:
        keys = sorted(list(AGENT._q_tables.keys()))
        return jsonify(
            {
                "step": int(AGENT._step),
                "epsilon": float(AGENT.epsilon),
                "keys": keys,
            }
        )


@app.get("/debug/qtable")
def debug_qtable():
    key = request.args.get("key")
    with AGENT._lock:
        if key:
            if key not in AGENT._q_tables:
                return jsonify({"error": "key not found"}), 404
            return jsonify(
                {
                    "key": key,
                    "actions": AGENT._actions.get(key, []),
                    "q": AGENT._q_tables[key].tolist(),
                    "epsilon": float(AGENT.epsilon),
                    "step": int(AGENT._step),
                }
            )
        out = {}
        for k, q in AGENT._q_tables.items():
            out[k] = {
                "actions": AGENT._actions.get(k, []),
                "q": q.tolist(),
            }
        return jsonify({"epsilon": float(AGENT.epsilon), "step": int(AGENT._step), "tables": out})


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
