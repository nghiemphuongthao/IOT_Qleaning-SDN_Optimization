#!/usr/bin/env python3

import time
import random
import threading
import subprocess
import json
from datetime import datetime

class TrafficGenerator:
    def __init__(self, target_network):
        self.target_network = target_network
        self.results = []
        # Define hosts in different subnets for realistic traffic patterns
        self.hosts = [
            '10.0.1.1', '10.0.1.2', '10.0.1.3',
            '10.0.2.1', '10.0.2.2',
            '10.0.3.1', '10.0.3.2', 
            '10.0.4.1', '10.0.4.2', '10.0.4.3',
            '10.0.100.2'
        ]
        
    def generate_mixed_traffic(self):
        """Generate mixed traffic patterns"""
        print("Starting mixed traffic generation...")
        
        # Cross-subnet traffic
        cross_subnet_thread = threading.Thread(target=self._cross_subnet_traffic)
        cross_subnet_thread.daemon = True
        cross_subnet_thread.start()
        
        # Intra-subnet traffic
        intra_subnet_thread = threading.Thread(target=self._intra_subnet_traffic)
        intra_subnet_thread.daemon = True
        intra_subnet_thread.start()
        
        # Cloud traffic
        cloud_traffic_thread = threading.Thread(target=self._cloud_traffic)
        cloud_traffic_thread.daemon = True
        cloud_traffic_thread.start()
    
    def _cross_subnet_traffic(self):
        """Generate traffic between different subnets"""
        while True:
            try:
                src = random.choice(self.hosts)
                dst = random.choice([h for h in self.hosts if h != src])
                bandwidth = random.choice(['10M', '5M', '20M'])
                duration = random.randint(10, 30)
                
                cmd = [
                    'iperf', '-c', dst, '-b', bandwidth,
                    '-t', str(duration), '-i', '1', '-p', '5001'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                self._log_traffic(f'cross_subnet_{src}_{dst}', result.stdout)
                time.sleep(random.randint(5, 15))
            except Exception as e:
                print(f"Cross-subnet traffic error: {e}")
                time.sleep(10)
    
    def _intra_subnet_traffic(self):
        """Generate traffic within the same subnet"""
        subnets = {
            'subnet1': ['10.0.1.1', '10.0.1.2', '10.0.1.3'],
            'subnet2': ['10.0.2.1', '10.0.2.2'],
            'subnet3': ['10.0.3.1', '10.0.3.2'],
            'subnet4': ['10.0.4.1', '10.0.4.2', '10.0.4.3'],
        }
        
        while True:
            try:
                subnet = random.choice(list(subnets.keys()))
                hosts = subnets[subnet]
                if len(hosts) >= 2:
                    src, dst = random.sample(hosts, 2)
                    bandwidth = random.choice(['1M', '5M', '10M'])
                    duration = random.randint(5, 20)
                    
                    cmd = [
                        'iperf', '-c', dst, '-b', bandwidth,
                        '-t', str(duration), '-i', '1', '-p', '5002'
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    self._log_traffic(f'intra_{subnet}_{src}_{dst}', result.stdout)
                time.sleep(random.randint(3, 10))
            except Exception as e:
                print(f"Intra-subnet traffic error: {e}")
                time.sleep(10)
    
    def _cloud_traffic(self):
        """Generate traffic to cloud server"""
        cloud_server = '10.0.100.2'
        sources = ['10.0.1.1', '10.0.2.1', '10.0.3.1', '10.0.4.1']
        
        while True:
            try:
                src = random.choice(sources)
                bandwidth = random.choice(['50M', '100M', '30M'])
                duration = random.randint(15, 45)
                
                cmd = [
                    'iperf', '-c', cloud_server, '-b', bandwidth,
                    '-t', str(duration), '-i', '1', '-p', '5003'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                self._log_traffic(f'cloud_{src}', result.stdout)
                time.sleep(random.randint(10, 20))
            except Exception as e:
                print(f"Cloud traffic error: {e}")
                time.sleep(10)
    
    def generate_latency_test(self):
        """Test latency between different network segments"""
        print("Starting latency tests...")
        
        test_pairs = [
            ('10.0.1.1', '10.0.100.2'),
            ('10.0.4.3', '10.0.1.2'),
            ('10.0.2.1', '10.0.3.1'),
        ]
        
        for src, dst in test_pairs:
            try:
                cmd = ['ping', '-c', '10', '-s', '64', '-i', '0.1', dst]
                result = subprocess.run(cmd, capture_output=True, text=True)
                self._log_traffic(f'latency_{src}_{dst}', result.stdout)
                time.sleep(2)
            except Exception as e:
                print(f"Latency test error for {src} to {dst}: {e}")
    
    def _log_traffic(self, traffic_type, output):
        """Log traffic results"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'type': traffic_type,
            'output': output
        }
        self.results.append(log_entry)
        
        # Save to file periodically
        if len(self.results) % 5 == 0:
            self._save_results()
    
    def _save_results(self):
        """Save results to JSON file"""
        try:
            with open('/shared/traffic_results.json', 'w') as f:
                json.dump(self.results, f, indent=2)
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def run_complete_scenario(self, duration=300):
        """Run complete traffic scenario"""
        print(f"Starting complete traffic scenario for {duration} seconds")
        
        # Start background traffic
        self.generate_mixed_traffic()
        
        # Run specific scenarios at intervals
        start_time = time.time()
        scenario_count = 0
        
        while time.time() - start_time < duration:
            current_time = time.time() - start_time
            
            if scenario_count == 0 and current_time > 60:
                print("=== Starting Latency Test ===")
                self.generate_latency_test()
                scenario_count += 1
            
            elif scenario_count == 1 and current_time > 180:
                print("=== Starting Intensive Traffic ===")
                # Already running mixed traffic
                scenario_count += 1
            
            time.sleep(10)
        
        # Final save
        self._save_results()
        print("Traffic generation completed")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 traffic.py <target_network>")
        sys.exit(1)
    
    target_network = sys.argv[1]
    generator = TrafficGenerator(target_network)
    
    # Run for 5 minutes
    generator.run_complete_scenario(300)