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

    def get_reward(
        self,
        load_bps: float,
        drops: int,
        stable_bonus: bool = False,
        backup_penalty: bool = False,
    ) -> float:
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0
        try:
            d = int(drops)
        except Exception:
            d = 0

        if d > 0:
            r = -50.0
        elif load < 0.5 * self.th:
            r = 20.0
        elif load < 1.0 * self.th:
            r = 10.0
        else:
            r = -5.0

        if stable_bonus:
            r += 5.0
        if backup_penalty:
            r -= 3.0
        return float(r)


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

    def switch_snapshot(self, dpid: int, ttl_s: float | None = None):
        now = time.time()
        with self._lock:
            items = []
            for k, v in self._metrics.items():
                if k.dpid != int(dpid):
                    continue
                if ttl_s is not None:
                    try:
                        ts = float(v.get("ts", 0.0))
                    except Exception:
                        ts = 0.0
                    if (now - ts) > float(ttl_s):
                        continue
                items.append((k, v))
        return items


THRESHOLD_BPS = float(os.environ.get("CONGESTION_THRESHOLD_BPS", "200000"))
MODEL = QoSModel(congestion_threshold=THRESHOLD_BPS)

METRICS_TTL_S = float(os.environ.get("QL_METRICS_TTL_S", "5"))

_backup_ports_env = (os.environ.get("QL_BACKUP_PORTS", "") or "").strip()
QL_BACKUP_PORTS = set()
if _backup_ports_env:
    try:
        QL_BACKUP_PORTS = {int(x.strip()) for x in _backup_ports_env.split(",") if x.strip()}
    except Exception:
        QL_BACKUP_PORTS = set()
AGENT = QAgent(
    lr=float(os.environ.get("QL_LR", "0.1")),
    gamma=float(os.environ.get("QL_GAMMA", "0.9")),
    epsilon=float(os.environ.get("QL_EPSILON", "1.0")),
    epsilon_min=float(os.environ.get("QL_EPSILON_MIN", "0.05")),
    epsilon_decay=float(os.environ.get("QL_EPSILON_DECAY", "0.995")),
)
STORE = StateStore()

PERSIST_PATH = Path(os.environ.get("QL_PERSIST_PATH", "/shared/logs/qlearning_qtables.json"))
PERSIST_EVERY_STEPS = int(os.environ.get("QL_PERSIST_EVERY_STEPS", "10"))

LOG_PATH = Path(os.environ.get("QL_LOG_PATH", "/shared/raw/qlearning_agent_log.csv"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_log_lock = threading.Lock()
_log_initialized = False

LEGACY_LOG_DIR = Path(os.environ.get("LOG_DIR", "/shared/logs"))
LEGACY_LOG_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_LOG_PATH = LEGACY_LOG_DIR / "qlearning_log.csv"
_legacy_log_lock = threading.Lock()
_legacy_log_initialized = False


def _load_persisted_agent_state():
    try:
        if not PERSIST_PATH.exists():
            return
        data = json.loads(PERSIST_PATH.read_text())
        tables = data.get("tables")
        if not isinstance(tables, dict):
            return
        with AGENT._lock:
            for key, item in tables.items():
                if not isinstance(item, dict):
                    continue
                actions = item.get("actions")
                q = item.get("q")
                if not isinstance(actions, list) or not isinstance(q, list):
                    continue
                try:
                    q_arr = np.array(q, dtype=np.float64)
                    if q_arr.ndim != 2 or q_arr.shape[0] != 3:
                        continue
                except Exception:
                    continue
                AGENT._q_tables[str(key)] = q_arr
                AGENT._actions[str(key)] = [int(x) for x in actions]
                AGENT._last[str(key)] = None

            eps = data.get("epsilon")
            step = data.get("step")
            if eps is not None:
                try:
                    AGENT.epsilon = float(eps)
                except Exception:
                    pass
            if step is not None:
                try:
                    AGENT._step = int(step)
                except Exception:
                    pass
    except Exception:
        return


def _persist_agent_state_locked():
    try:
        PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "version": 1,
            "epsilon": float(AGENT.epsilon),
            "step": int(AGENT._step),
            "tables": {},
        }
        for key, q in AGENT._q_tables.items():
            try:
                q_list = q.tolist()
            except Exception:
                continue
            out["tables"][str(key)] = {
                "actions": [int(x) for x in AGENT._actions.get(key, [])],
                "q": q_list,
            }
        PERSIST_PATH.write_text(json.dumps(out))
    except Exception:
        return


def _init_log_files():
    global _log_initialized
    global _legacy_log_initialized

    try:
        with _log_lock:
            if not LOG_PATH.exists():
                with LOG_PATH.open("a", newline="") as f:
                    w = csv.writer(f)
                    header = [
                        "ts", "step", "dpid", "dst_prefix", "state", "action", "out_port",
                        "epsilon", "max_load_bps", "total_drops", "reward", "q_values",
                    ]
                    header.extend(["queue_id", "meter_rate_kbps"])
                    w.writerow(header)
            _log_initialized = True
    except Exception:
        pass

    try:
        with _legacy_log_lock:
            if not LEGACY_LOG_PATH.exists():
                with LEGACY_LOG_PATH.open("a", newline="") as f:
                    w = csv.writer(f)
                    w.writerow([
                        "time",
                        "step",
                        "state",
                        "action",
                        "reward",
                        "load",
                        "drops",
                        "epsilon",
                        "max_q",
                        "dpid",
                        "dst_prefix",
                        "out_port",
                        "queue_id",
                        "meter_rate_kbps",
                    ])
            _legacy_log_initialized = True
    except Exception:
        pass


app = Flask(__name__)

_init_log_files()
_load_persisted_agent_state()


def _flow_key(dpid: int, dst_prefix: str) -> str:
    return f"{int(dpid)}:{dst_prefix}"


def _compute_ports_state(dpid: int, ports: list[int] | None) -> tuple[int, float, int]:
    snap = STORE.switch_snapshot(dpid, ttl_s=METRICS_TTL_S)
    if not snap:
        return 0, 0.0, 0

    port_set = None
    if ports:
        port_set = {int(p) for p in ports}

    max_load = 0.0
    total_drops = 0
    for k, v in snap:
        if port_set is not None and int(k.port) not in port_set:
            continue
        max_load = max(max_load, float(v.get("load_bps", 0.0)))
        total_drops += int(v.get("drops", 0))

    state = MODEL.get_state(load_bps=max_load, drops=total_drops)
    return state, max_load, total_drops


def _compute_port_metrics(dpid: int, port: int) -> tuple[float, int]:
    snap = STORE.switch_snapshot(dpid, ttl_s=METRICS_TTL_S)
    if not snap:
        return 0.0, 0

    max_load = 0.0
    total_drops = 0
    for k, v in snap:
        if int(k.port) != int(port):
            continue
        max_load = max(max_load, float(v.get("load_bps", 0.0)))
        total_drops += int(v.get("drops", 0))
    return max_load, total_drops


def _compute_queue_metrics(dpid: int, port: int, qid: int) -> tuple[float, int]:
    snap = STORE.switch_snapshot(dpid, ttl_s=METRICS_TTL_S)
    if not snap:
        return 0.0, 0

    max_load = 0.0
    total_drops = 0
    for k, v in snap:
        if int(k.port) != int(port) or k.qid is None or int(k.qid) != int(qid):
            continue
        max_load = max(max_load, float(v.get("load_bps", 0.0)))
        total_drops += int(v.get("drops", 0))
    return max_load, total_drops


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
    state, max_load, total_drops = _compute_ports_state(dpid, ports=None)
    return jsonify({"state": state, "max_load_bps": max_load, "total_drops": total_drops})


@app.post("/act")
def act():
    body = request.get_json(force=True, silent=True) or {}
    dpid = int(body.get("dpid"))
    dst_prefix = str(body.get("dst_prefix"))
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return jsonify({"error": "candidates required"}), 400

    # New format: candidates are list of {"action_idx": X, "out_port": Y, "queue_id": Z, "meter_rate_kbps": W}
    if isinstance(candidates[0], dict) and "action_idx" in candidates[0]:
        # New QoS action space format
        cand_actions = [(int(c["action_idx"]), int(c["out_port"]), int(c["queue_id"]), int(c["meter_rate_kbps"])) for c in candidates]
        action_indices = [a[0] for a in cand_actions]
        ports_for_state = list(set([a[1] for a in cand_actions]))  # Unique ports for state computation
    else:
        # Legacy format: candidates are just port numbers
        cand_ports = [int(p) for p in candidates]
        action_indices = cand_ports
        ports_for_state = cand_ports
        cand_actions = None

    state, max_load, total_drops = _compute_ports_state(dpid, ports=ports_for_state)
    key = _flow_key(dpid, dst_prefix)

    reward = None

    with AGENT._lock:
        AGENT._ensure_key(key, action_indices)
        a_col = AGENT.choose_action(key, state)
        action_id = int(AGENT._actions[key][a_col])
        
        if cand_actions is not None:
            # New format: return action_idx and look up details
            chosen_action = next((a for a in cand_actions if a[0] == action_id), None)
            if chosen_action:
                out_port, queue_id, meter_rate = chosen_action[1], chosen_action[2], chosen_action[3]
            else:
                out_port, queue_id, meter_rate = cand_actions[0][1], cand_actions[0][2], cand_actions[0][3]
        else:
            # Legacy format: action_idx is the port
            out_port = int(action_id)
            queue_id, meter_rate = None, None

        prev = AGENT._last.get(key)
        if prev is not None:
            try:
                s_prev, a_prev, out_prev, q_prev = prev
            except Exception:
                s_prev, a_prev, out_prev = prev
                q_prev = None

            if q_prev is not None:
                prev_load, prev_drops = _compute_queue_metrics(dpid, int(out_prev), int(q_prev))
            else:
                prev_load, prev_drops = _compute_port_metrics(dpid, int(out_prev))

            stable_bonus = (int(a_prev) == int(a_col))
            backup_penalty = (int(out_prev) in QL_BACKUP_PORTS) if QL_BACKUP_PORTS else False
            r = MODEL.get_reward(
                load_bps=prev_load,
                drops=prev_drops,
                stable_bonus=stable_bonus,
                backup_penalty=backup_penalty,
            )
            reward = float(r)
            AGENT.learn(key, s=s_prev, a=a_prev, r=r, s_next=state)

        AGENT._last[key] = (state, int(a_col), int(out_port), (None if queue_id is None else int(queue_id)))
        AGENT._step += 1
        step = AGENT._step

        if PERSIST_EVERY_STEPS > 0 and int(step) % int(PERSIST_EVERY_STEPS) == 0:
            _persist_agent_state_locked()

        q_snapshot = None
        try:
            q_snapshot = AGENT._q_tables[key][state].tolist()
        except Exception:
            q_snapshot = None

        eps = float(AGENT.epsilon)

    # Response format: always return action_id, include QoS details if available
    response_data = {
        "action": int(action_id),
        "state": int(state),
        "epsilon": float(eps),
        "step": int(step),
        "max_load_bps": float(max_load),
        "total_drops": int(total_drops),
    }
    
    if queue_id is not None and meter_rate is not None:
        response_data["out_port"] = int(out_port)
        response_data["queue_id"] = int(queue_id)
        response_data["meter_rate_kbps"] = int(meter_rate)
    else:
        response_data["out_port"] = int(out_port)
    
    if reward is not None:
        response_data["reward"] = float(reward)
    
    if q_snapshot is not None:
        response_data["q_values"] = q_snapshot
    
    # Logging
    global _log_initialized
    try:
        with _log_lock:
            if not _log_initialized or not LOG_PATH.exists():
                with LOG_PATH.open("a", newline="") as f:
                    w = csv.writer(f)
                    header = [
                        "ts", "step", "dpid", "dst_prefix", "state", "action", "out_port",
                        "epsilon", "max_load_bps", "total_drops", "reward", "q_values"
                    ]
                    header.extend(["queue_id", "meter_rate_kbps"])
                    w.writerow(header)
                _log_initialized = True

            with LOG_PATH.open("a", newline="") as f:
                w = csv.writer(f)
                row = [
                    float(time.time()), int(step), int(dpid), str(dst_prefix), int(state),
                    int(action_id), int(out_port), float(eps), float(max_load), int(total_drops)
                ]
                if reward is not None:
                    row.append(float(reward))
                else:
                    row.append("")
                if q_snapshot is not None:
                    row.append(str(q_snapshot))
                else:
                    row.append("")
                if queue_id is not None:
                    row.append(int(queue_id))
                else:
                    row.append("")
                if meter_rate is not None:
                    row.append(int(meter_rate))
                else:
                    row.append("")
                w.writerow(row)
    except Exception:
        pass  # Logging errors shouldn't break the API

    global _legacy_log_initialized
    try:
        if reward is not None:
            max_q = ""
            try:
                if q_snapshot is not None and isinstance(q_snapshot, list) and q_snapshot:
                    max_q = float(max(q_snapshot))
            except Exception:
                max_q = ""

            with _legacy_log_lock:
                if not _legacy_log_initialized or not LEGACY_LOG_PATH.exists():
                    with LEGACY_LOG_PATH.open("a", newline="") as f:
                        w = csv.writer(f)
                        w.writerow([
                            "time",
                            "step",
                            "state",
                            "action",
                            "reward",
                            "load",
                            "drops",
                            "epsilon",
                            "max_q",
                            "dpid",
                            "dst_prefix",
                            "out_port",
                            "queue_id",
                            "meter_rate_kbps",
                        ])
                    _legacy_log_initialized = True

                with LEGACY_LOG_PATH.open("a", newline="") as f:
                    w = csv.writer(f)
                    w.writerow([
                        float(time.time()),
                        int(step),
                        int(state),
                        int(action_id),
                        float(reward),
                        float(max_load),
                        int(total_drops),
                        float(eps),
                        max_q,
                        int(dpid),
                        str(dst_prefix),
                        int(out_port),
                        ("" if queue_id is None else int(queue_id)),
                        ("" if meter_rate is None else int(meter_rate)),
                    ])
    except Exception:
        pass

    return jsonify(response_data)


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
