import numpy as np
import random

class QAgent:
    ACTION_MAP = {
        0: (100, 0),    # 100% qua Port 1
        1: (70, 30),     # 70% qua Port 1, 30% qua Port 5
        2: (50, 50),     # 50% qua Port 1, 50% qua Port 5
        3: (0, 100)      # 100% qua Port 5
    }

    def __init__(self, n_states=3, n_actions=4, alpha=0.1, gamma=0.95, epsilon=0.3):
        self.n_states = n_states
        self.n_actions = n_actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        
        self.q_table = np.zeros((n_states, n_actions))

        self.action_names = {
            0: "100:0 (P1)", 
            1: "70:30", 
            2: "50:50", 
            3: "0:100 (P5)"
        }

    def choose_action(self, state):
        if random.uniform(0, 1) < self.epsilon:
            return random.randint(0, self.n_actions - 1)
        return int(np.argmax(self.q_table[state]))

    def learn(self, old_state, action, reward, new_state):
        old_q = self.q_table[old_state, action]
        future_max = np.max(self.q_table[new_state])
        new_q = old_q + self.alpha * (reward + self.gamma * future_max - old_q)
        self.q_table[old_state, action] = new_q
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def get_best_action(self, state):
        return int(np.argmax(self.q_table[state]))

    def print_q_table(self):
        print("\n=== Q-Table (SW256 → Cloud 10.0.100) ===")
        print("State        | 100:0 (P1) | 70:30      | 50:50      | 0:100 (P5) | Best Action")
        states = ["Low Load   ", "Medium Load", "High Load  "]
        
        header_line = "-" * (13 + 12 * 4 + 13)
        print(header_line)

        for s in range(self.n_states):
            best = self.action_names[self.get_best_action(s)]
            q_values = [f"{v:10.2f}" for v in self.q_table[s]]
            print(f"{states[s]} | {' | '.join(q_values)} | {best}")
        print(header_line)