import os
import numpy as np

# --- discretization config (tune these to your observed ranges) ---
DELAY_BINS = 6      # e.g., 0..MAX_DELAY split into bins
LOSS_BINS = 4
QUEUE_BINS = 5
ENERGY_BINS = 5

MAX_DELAY = 1000.0    # ms
MAX_LOSS = 100.0      # %
MAX_QUEUE = 1000.0    # pkts
MAX_ENERGY = 100.0    # arbitrary units

ACTIONS = [
    "PATH_G1",
    "PATH_G2",
    "INSTALL_METER",
    "PRIORITIZE_CRITICAL"
]

NUM_ACTIONS = len(ACTIONS)

# Derived
STATE_BINS = (DELAY_BINS, LOSS_BINS, QUEUE_BINS, ENERGY_BINS)
NUM_STATES = DELAY_BINS * LOSS_BINS * QUEUE_BINS * ENERGY_BINS


def _discretize(val, maxval, bins):
    v = float(val)
    if v <= 0:
        return 0
    if v >= maxval:
        return bins - 1
    # linear map
    ratio = v / maxval
    idx = int(ratio * (bins - 1) + 0.5)
    return max(0, min(bins - 1, idx))


def encode_state(metrics):
    """
    metrics: dict with keys: delay (ms), loss (%), queue (pkts), energy (units)
    returns: integer state index in [0, NUM_STATES-1]
    """
    d = _discretize(metrics.get("delay", 0.0), MAX_DELAY, DELAY_BINS)
    l = _discretize(metrics.get("loss", 0.0), MAX_LOSS, LOSS_BINS)
    q = _discretize(metrics.get("queue", 0.0), MAX_QUEUE, QUEUE_BINS)
    e = _discretize(metrics.get("energy", 0.0), MAX_ENERGY, ENERGY_BINS)
    # flatten multi-index: (((d * LOSS)+l) * QUEUE + q) * ENERGY + e
    idx = (((d * LOSS_BINS) + l) * QUEUE_BINS + q) * ENERGY_BINS + e
    return int(idx)


class QTable:
    def __init__(self, path=None):
        self.path = path or "/shared/qtable.npy"
        self.num_states = NUM_STATES
        self.num_actions = NUM_ACTIONS
        self.table = None
        self._init_table()

    def _init_table(self):
        if self.path and os.path.exists(self.path):
            try:
                self.table = np.load(self.path)
                assert self.table.shape == (self.num_states, self.num_actions)
                return
            except Exception:
                # fallback to init new
                pass
        self.table = np.zeros((self.num_states, self.num_actions), dtype=np.float32)

    def save(self, path=None):
        p = path or self.path
        if p:
            try:
                np.save(p, self.table)
                return True
            except Exception as e:
                print("QTable.save error:", e)
                return False
        return False

    def load(self, path=None):
        p = path or self.path
        if p and os.path.exists(p):
            self.table = np.load(p)
            return True
        return False

    def get_action_values(self, state_idx):
        return self.table[state_idx]

    def update(self, s, a, target, alpha=0.2):
        # simple incremental update (Q-learning)
        self.table[s, a] = (1 - alpha) * self.table[s, a] + alpha * target

    def argmax(self, s):
        return int(np.argmax(self.table[s]))

    def best_value(self, s):
        return float(np.max(self.table[s]))