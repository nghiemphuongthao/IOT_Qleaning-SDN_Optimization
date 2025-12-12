import os
import numpy as np

ACTIONS = ["A0", "A1", "A2"]

def encode_state(metrics):
    util = float(metrics.get("avg_util_mbps", 0.0))
    drop = float(metrics.get("tx_dropped", 0.0) or metrics.get("loss", 0.0))

    if util < 3.0:
        util_bin = 0
    elif util < 7.0:
        util_bin = 1
    else:
        util_bin = 2

    drop_bin = 1 if drop > 0 else 0
    return util_bin * 2 + drop_bin  # 0..5

class QTable:
    def __init__(self, path="/shared/qtable.npy", n_states=6, n_actions=3):
        self.path = path
        self.q = np.zeros((n_states, n_actions), dtype=np.float32)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                arr = np.load(self.path)
                if arr.shape == self.q.shape:
                    self.q[:] = arr
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        np.save(self.path, self.q)

    def argmax(self, s):
        return int(np.argmax(self.q[s]))

    def best_value(self, s):
        return float(np.max(self.q[s]))

    def update(self, s, a, target, alpha=0.2):
        self.q[s, a] = (1 - alpha) * self.q[s, a] + alpha * target
