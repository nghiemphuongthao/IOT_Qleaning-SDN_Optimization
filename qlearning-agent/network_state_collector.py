import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NetworkStateCollector:
    def __init__(self, controller_url="http://ryu-controller:8080"):
        self.controller_url = controller_url

    def get_network_stats(self):
        try:
            response = requests.get(f"{self.controller_url}/stats/flow/1")
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get stats: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error collecting network state: {e}")
            return None

    def get_switch_stats(self):
        try:
            response = requests.get(f"{self.controller_url}/stats/port/1")
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get switch stats: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error collecting switch stats: {e}")
            return None

    def collect_state(self):
        flow_stats = self.get_network_stats()
        port_stats = self.get_switch_stats()
        
        state = {
            'timestamp': time.time(),
            'flow_stats': flow_stats,
            'port_stats': port_stats
        }
        
        return state