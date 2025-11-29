import os

class ExperimentConfig:
    def __init__(self):
        self.mode = os.getenv('MODE', 'baseline')
        self.setup_mode_config()
    
    def setup_mode_config(self):
        if self.mode == 'baseline':
            self.controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1')
            self.controller_port = int(os.getenv('CONTROLLER_PORT', 6633))
            self.ryu_app = 'app.py'  # Basic forwarding
            
        elif self.mode == 'sdn':
            self.controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1') 
            self.controller_port = int(os.getenv('CONTROLLER_PORT', 6633))
            self.ryu_app = 'app.py'  # SDN features
            
        elif self.mode == 'sdn_qlearning':
            self.controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1')
            self.controller_port = int(os.getenv('CONTROLLER_PORT', 6633))
            self.ryu_app = 'app.py'  # With Q-learning hooks
            self.qlearning_enabled = True
            
    def get_controller_endpoint(self):
        return f"http://{self.controller_ip}:{8080}"

# Sử dụng trong Ryu controller
config = ExperimentConfig()