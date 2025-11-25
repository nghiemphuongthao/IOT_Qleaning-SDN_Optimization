#!/usr/bin/env python3
"""
Q-learning Agent for SDN Traffic Optimization - Hoàn chỉnh
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
import random
from collections import deque
import json
import time
import os
import requests

class DQNAgent:
    """Deep Q-Network Agent for SDN Traffic Optimization"""
    
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=10000)
        self.gamma = 0.95    # discount rate
        self.epsilon = 1.0   # exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.model = self._build_model()
        self.target_model = self._build_model()
        self.update_target_network()
        
        # Metrics tracking
        self.training_history = []
        
        # Ryu controller API endpoint
        self.ryu_base_url = "http://ryu-controller:8080"
        
    def _build_model(self):
        """Xây dựng Neural Network cho Q-learning"""
        model = models.Sequential()
        model.add(layers.Dense(64, input_dim=self.state_size, activation='relu'))
        model.add(layers.Dense(64, activation='relu'))
        model.add(layers.Dense(32, activation='relu'))
        model.add(layers.Dense(self.action_size, activation='linear'))
        model.compile(loss='mse', optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate))
        return model
    
    def update_target_network(self):
        """Cập nhật target network"""
        self.target_model.set_weights(self.model.get_weights())
    
    def remember(self, state, action, reward, next_state, done):
        """Lưu experience vào memory"""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state):
        """Chọn action dựa trên epsilon-greedy policy"""
        if np.random.random() <= self.epsilon:
            return random.randrange(self.action_size)
        act_values = self.model.predict(state, verbose=0)
        return np.argmax(act_values[0])
    
    def replay(self, batch_size=32):
        """Training với batch từ memory"""
        if len(self.memory) < batch_size:
            return
        
        minibatch = random.sample(self.memory, batch_size)
        
        for state, action, reward, next_state, done in minibatch:
            target = reward
            if not done:
                target = reward + self.gamma * np.amax(self.target_model.predict(next_state, verbose=0)[0])
            
            target_f = self.model.predict(state, verbose=0)
            target_f[0][action] = target
            
            self.model.fit(state, target_f, epochs=1, verbose=0)
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def load(self, name):
        self.model.load_weights(name)
    
    def save(self, name):
        self.model.save_weights(name)

class SDNQLearningOptimizer:
    """Lớp chính tích hợp Q-learning với SDN"""
    
    def __init__(self):
        self.state_size = 15  # Các metrics: throughput, latency, loss, utilization, etc.
        self.action_size = 5   # Các actions: route changes, QoS adjustments, etc.
        
        self.agent = DQNAgent(self.state_size, self.action_size)
        self.current_state = None
        self.episode = 0
        
        # Kết nối tới Ryu controller
        self.ryu_base_url = "http://ryu-controller:8080"
        
    def get_network_state(self):
        """Lấy network state từ Ryu controller và metrics"""
        try:
            # Gọi API để lấy metrics từ Ryu (giả định có API)
            response = requests.get(f"{self.ryu_base_url}/stats/network", timeout=5)
            if response.status_code == 200:
                metrics = response.json()
            else:
                metrics = self._get_fallback_metrics()
        except:
            metrics = self._get_fallback_metrics()
        
        # Chuyển đổi metrics thành state vector
        state = np.array([
            metrics.get('throughput', 0) / 1000,  # Normalize
            metrics.get('latency', 0) / 100,      # Normalize
            metrics.get('packet_loss', 0),
            metrics.get('jitter', 0) / 10,        # Normalize
            metrics.get('energy_consumption', 0) / 100,
            metrics.get('active_flows', 0) / 100,
            metrics.get('switch_count', 0) / 10,
            metrics.get('link_utilization', 0) / 100,
            random.random(),  # Placeholder cho các metrics khác
            random.random(),
            random.random(),
            random.random(),
            random.random(),
            random.random(),
            random.random()
        ])
        return state.reshape(1, -1)
    
    def _get_fallback_metrics(self):
        """Fallback metrics nếu không kết nối được Ryu"""
        return {
            'throughput': random.uniform(50, 100),
            'latency': random.uniform(1, 10),
            'packet_loss': random.uniform(0, 5),
            'jitter': random.uniform(0.5, 2),
            'energy_consumption': random.uniform(50, 200),
            'active_flows': random.randint(10, 50),
            'switch_count': 5,
            'link_utilization': random.uniform(30, 80)
        }
    
    def calculate_reward(self, old_metrics, new_metrics):
        """Tính reward dựa trên sự cải thiện performance"""
        reward = 0
        
        # Reward cho throughput improvement
        if new_metrics['throughput'] > old_metrics['throughput']:
            reward += 1
        else:
            reward -= 1
            
        # Reward cho latency reduction
        if new_metrics['latency'] < old_metrics['latency']:
            reward += 2
        else:
            reward -= 2
            
        # Penalty cho packet loss
        reward -= new_metrics['packet_loss'] * 10
        
        # Reward cho energy efficiency
        if new_metrics['energy_consumption'] < old_metrics['energy_consumption']:
            reward += 0.5
            
        return reward
    
    def execute_action(self, action):
        """Thực thi action trên SDN controller"""
        action_map = {
            0: {"type": "optimize_shortest_path", "params": {"algorithm": "dijkstra"}},
            1: {"type": "load_balance", "params": {"method": "round_robin"}},
            2: {"type": "qos_prioritize", "params": {"traffic_type": "video"}},
            3: {"type": "energy_saving", "params": {"mode": "aggressive"}},
            4: {"type": "redundant_routing", "params": {"backup_paths": 2}}
        }
        
        action_config = action_map.get(action, action_map[0])
        
        try:
            # Gửi action tới Ryu controller
            response = requests.post(
                f"{self.ryu_base_url}/qlearning/action",
                json=action_config,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ Action {action} executed: {action_config['type']}")
                return True
            else:
                print(f"❌ Failed to execute action {action}")
                return False
                
        except Exception as e:
            print(f"❌ Error executing action: {e}")
            return False
    
    def train_episode(self):
        """Training một episode hoàn chỉnh"""
        print(f"Starting training episode {self.episode}")
        
        # Lấy initial state
        state = self.get_network_state()
        total_reward = 0
        old_metrics = self._get_current_metrics()
        
        for step in range(100):  # 100 steps per episode
            action = self.agent.act(state)
            
            # Thực thi action
            success = self.execute_action(action)
            
            if success:
                # Chờ một chút để thấy hiệu ứng
                time.sleep(2)
                
                # Lấy new state
                next_state = self.get_network_state()
                new_metrics = self._get_current_metrics()
                
                # Tính reward
                reward = self.calculate_reward(old_metrics, new_metrics)
                done = step == 99  # Kết thúc episode
                
                self.agent.remember(state, action, reward, next_state, done)
                state = next_state
                total_reward += reward
                old_metrics = new_metrics
                
                if done:
                    break
        
        # Training với experience replay
        if len(self.agent.memory) > 32:
            self.agent.replay(32)
            
        self.episode += 1
        
        # Log training progress
        training_info = {
            'episode': self.episode,
            'total_reward': total_reward,
            'epsilon': self.agent.epsilon,
            'memory_size': len(self.agent.memory)
        }
        self.agent.training_history.append(training_info)
        
        print(f"Episode {self.episode} completed. Total reward: {total_reward}")
        return total_reward
    
    def _get_current_metrics(self):
        """Lấy metrics hiện tại (giả lập)"""
        return {
            'throughput': random.uniform(50, 100),
            'latency': random.uniform(1, 10),
            'packet_loss': random.uniform(0, 5),
            'energy_consumption': random.uniform(50, 200)
        }
    
    def run_training(self, total_episodes=1000):
        """Chạy training loop"""
        print(f"Starting Q-learning training for {total_episodes} episodes")
        
        for episode in range(total_episodes):
            reward = self.train_episode()
            
            # Log progress mỗi 10 episodes
            if episode % 10 == 0:
                print(f"Episode {episode}: Reward={reward}, Epsilon={self.agent.epsilon:.3f}")
            
            # Save model mỗi 100 episodes
            if episode % 100 == 0:
                self.save_model(f"models/qlearning_model_ep{episode}.h5")
        
        print("Training completed!")
        self.save_model("models/qlearning_model_final.h5")
    
    def save_model(self, filename):
        """Lưu model"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.agent.save(filename)
        print(f"💾 Model saved: {filename}")
    
    def load_model(self, filename):
        """Load model"""
        self.agent.load(filename)
        print(f"Model loaded: {filename}")
    
    def save_training_history(self):
        """Lưu lịch sử training"""
        os.makedirs('results', exist_ok=True)
        with open('results/training_history.json', 'w') as f:
            json.dump(self.agent.training_history, f, indent=2)
        print("Training history saved")

def main():
    """Main function"""
    print("=" * 60)
    print("Q-LEARNING AGENT FOR SDN OPTIMIZATION")
    print("=" * 60)
    
    optimizer = SDNQLearningOptimizer()
    
    # Chạy training
    optimizer.run_training(total_episodes=100)
    
    # Lưu kết quả
    optimizer.save_training_history()
    
    print("Q-learning agent finished!")

if __name__ == "__main__":
    main()