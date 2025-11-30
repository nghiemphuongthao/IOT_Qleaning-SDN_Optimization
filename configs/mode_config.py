import os
import sys

class ExperimentConfig:
    def __init__(self):
        self.mode = os.getenv('MODE', 'baseline')
        self.setup_mode_config()
    
    def setup_mode_config(self):
        if self.mode == 'baseline':
            self.controller_ip = None
            self.controller_port = None
            self.ryu_app = None
            self.qlearning_enabled = False 
            self.topo_file = 'topology_baseline.py'  # Basic forwarding
            
        elif self.mode == 'sdn':
            self.controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1') 
            self.controller_port = int(os.getenv('CONTROLLER_PORT', 6633))
            self.ryu_app = 'app.py'  # SDN features
            self.qlearning_enabled = False
            self.topo_file = 'topology_sdn.py'
            
        elif self.mode == 'sdn_qlearning':
            self.controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1')
            self.controller_port = int(os.getenv('CONTROLLER_PORT', 6633))
            self.ryu_app = 'app.py'  # With Q-learning hooks
            self.qlearning_enabled = True
            self.topo_file = 'topology_sdn.py'
            
    def get_controller_endpoint(self):
        return f"http://{self.controller_ip}:{8080}"

    def load_topology(self):
        if self.topo_file:
            topo_module = __import__(self.topo_file.replace('.py', ''))  
            return topo_module
        else:
            print("No topology file defined for this mode.")
            sys.exit(1)