import numpy as np
import random
import logging
import yaml
import os
import time
from network_state_collector import NetworkStateCollector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class QLearningAgent:
    def __init__(self, state_size, action_size, learning_rate=0.1, discount_factor=0.9, exploration_rate=0.1):
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.q_table = np.zeros((state_size, action_size))
        
    def choose_action(self, state):
        if random.uniform(0, 1) < self.exploration_rate:
            return random.randint(0, self.action_size - 1)
        else:
            return np.argmax(self.q_table[state])
    
    def update_q_value(self, state, action, reward, next_state):
        current_q = self.q_table[state][action]
        max_next_q = np.max(self.q_table[next_state])
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        self.q_table[state][action] = new_q
    
    def save_model(self, filepath):
        np.save(filepath, self.q_table)
        logging.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath):
        self.q_table = np.load(filepath)
        logging.info(f"Model loaded from {filepath}")

def load_config():
    config_path = '/app/configs/experiment.yaml'
    if not os.path.exists(config_path):
        config_path = 'configs/experiment.yaml'
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def main():
    # Chờ các service khác khởi động
    logging.info("Waiting for other services to start...")
    time.sleep(10)
    
    config = load_config()
    ql_config = config['qlearning']
    
    agent = QLearningAgent(
        state_size=ql_config['state_size'],
        action_size=ql_config['action_size'],
        learning_rate=ql_config['learning_rate'],
        discount_factor=ql_config['discount_factor'],
        exploration_rate=ql_config['exploration_rate']
    )
    
    collector = NetworkStateCollector()
    
    logging.info("Q-learning agent started")
    
    for episode in range(100):
        state = random.randint(0, ql_config['state_size'] - 1)
        total_reward = 0
        
        for step in range(50):
            action = agent.choose_action(state)
            next_state = random.randint(0, ql_config['state_size'] - 1)
            reward = random.uniform(-1, 1)
            
            agent.update_q_value(state, action, reward, next_state)
            total_reward += reward
            state = next_state
            
        if episode % 10 == 0:
            logging.info(f"Episode: {episode}, Total Reward: {total_reward:.4f}")
    
    agent.save_model("/shared/q_table.npy")
    logging.info("Training completed")

if __name__ == "__main__":
    main()