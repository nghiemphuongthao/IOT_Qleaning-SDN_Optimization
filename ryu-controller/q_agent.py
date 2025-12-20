import numpy as np
import random
import csv
import time

LOG_PATH = "/app/shared/logs/qlearning_log.csv"
QTABLE_PATH = "/app/shared/logs/qtable.csv"                                        

class QAgent:
    def __init__(self, n_states, n_actions,
                 lr=0.1, gamma=0.9,
                 epsilon=1.0, epsilon_min=0.05, epsilon_decay=0.995):

        self.n_states = n_states
        self.n_actions = n_actions
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

        self.step = 0

        self.q_table = np.zeros((n_states, n_actions))

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, self.n_actions - 1)
        return int(np.argmax(self.q_table[state]))

def learn(self, s, a, r, s_next, load=0, drops=0):
    self.step += 1

    predict = self.q_table[s][a]
    target = r + self.gamma * np.max(self.q_table[s_next])
    self.q_table[s][a] += self.lr * (target - predict)

    max_q = np.max(self.q_table[s])

    # epsilon decay
    if self.epsilon > self.epsilon_min:
        self.epsilon *= self.epsilon_decay

    # ==== LOG Q-LEARNING ====
    self._log_internal(
        state=s,
        action=a,
        reward=r,
        load=load,
        drops=drops,
        max_q=max_q
    )


    # ===== LOG CHO ĐỒ ÁN =====
    def _log_internal(self, state, action, reward, load, drops, max_q):
        with open(LOG_PATH, "a", newline="") as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow([
                    "time",
                    "step",
                    "state",
                    "action",
                    "reward",
                    "load",
                    "drops",
                    "epsilon",
                    "max_q"
                ])
            writer.writerow([
                time.time(),
                self.step,
                state,
                action,
                round(reward, 3),
                load,
                drops,
                round(self.epsilon, 3),
                round(max_q, 3)
            ])


    def export_q_table(self, filename="qtable.csv"):
        with open(QTABLE_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["State\\Action", 0, 1, 2, 3])
            for s in range(self.n_states):
                writer.writerow([s] + list(self.q_table[s]))

    def print_q_table(self):
        print("\nQ-TABLE:")
        for s in range(self.n_states):
            print(f"State {s}: {self.q_table[s]}")
