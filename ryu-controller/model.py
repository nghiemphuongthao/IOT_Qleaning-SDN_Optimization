# ryu-controller/model.py

class QoSModel:
    """
    QoSModel defines the RL problem (MDP):
    - State: discrete congestion level derived from (load_bps, drops)
      0 = LOW, 1 = MED, 2 = HIGH (or drops>0)
    - Reward: penalize drops strongly, encourage stable/no-drop operation.
    """

    def __init__(self, congestion_threshold: float):
        # bytes per second threshold used by controller
        self.th = float(congestion_threshold)

    def get_state(self, load_bps: float, drops: int) -> int:
        """
        Convert observed metrics into a discrete state index for Q-table.
        """
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0

        try:
            d = int(drops)
        except Exception:
            d = 0

        # Drops => worst state immediately
        if d > 0:
            return 2

        # Otherwise based on load
        if load < 0.5 * self.th:
            return 0
        elif load < 1.0 * self.th:
            return 1
        else:
            return 2

    def get_reward(
        self,
        load_bps: float,
        drops: int,
        stable_bonus: bool = False,
        backup_penalty: bool = False
    ) -> float:
        """
        Reward shaped for QoS (minimize packet loss):
        - Strong penalty on drops.
        - Positive reward when no drops.
        - Slight penalty when load is very high (risk of congestion).
        - Optional: stable_bonus / backup_penalty matching controller logic.
        """
        try:
            load = float(load_bps)
        except Exception:
            load = 0.0

        try:
            d = int(drops)
        except Exception:
            d = 0

        # Base reward
        if d > 0:
            r = -50.0
        else:
            if load < 0.5 * self.th:
                r = 20.0
            elif load < 1.0 * self.th:
                r = 10.0
            else:
                r = -5.0

        # Encourage stability (same action as previous)
        if stable_bonus:
            r += 5.0

        # Penalize using backup path unnecessarily
        if backup_penalty:
            r -= 3.0

        return float(r)
