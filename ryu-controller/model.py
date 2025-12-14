class QTable:
    def __init__(self, actions, alpha=0.7, gamma=0.8):
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.table = {}

    def get_state(self, state):
        if state not in self.table:
            self.table[state] = {a: 0.0 for a in self.actions}
        return self.table[state]

    def best_action(self, state):
        q_state = self.get_state(state)
        return max(q_state, key=q_state.get)

    def update(self, state, action, reward, next_state):
        q_state = self.get_state(state)
        q_next = self.get_state(next_state)

        old_value = q_state[action]
        new_value = old_value + self.alpha * (
            reward + self.gamma * max(q_next.values()) - old_value
        )

        q_state[action] = new_value

        # LOG HỘI TỤ (BẮT BUỘC)
        print(f"[Q] S={state} A={action} R={reward} Q={new_value:.2f}")
