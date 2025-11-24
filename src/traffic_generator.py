#!/usr/bin/env python3
"""
IoT Traffic Generator - Tạo traffic thực tế cho mạng IoT
"""

import time
import random
import threading
import json
from datetime import datetime
import os

class IoTTrafficGenerator:
    def __init__(self, net):
        self.net = net
        self.running = False
        self.threads = []
        
        # Các pattern traffic cho IoT
        self.traffic_patterns = {
            'smart_home': {
                'interval': (5, 30),  # 5-30 seconds between packets
                'size': (64, 512),    # 64-512 bytes
                'protocol': 'UDP',
                'destinations': ['10.0.1.10', '10.0.1.1']  # server or gateway
            },
            'industrial': {
                'interval': (1, 10),   # 1-10 seconds
                'size': (128, 1024),   # 128-1024 bytes
                'protocol': 'TCP',
                'destinations': ['10.0.1.10']
            },
            'healthcare': {
                'interval': (2, 15),   # 2-15 seconds  
                'size': (256, 2048),   # 256-2048 bytes
                'protocol': 'UDP',
                'destinations': ['10.0.1.10', '10.0.1.1']
            },
            'environmental': {
                'interval': (10, 60),  # 10-60 seconds
                'size': (512, 4096),   # 512-4096 bytes
                'protocol': 'TCP',
                'destinations': ['10.0.1.10']
            }
        }
        
        # Map devices to traffic patterns
        self.device_patterns = {
            'motion_sensor': 'smart_home',
            'temp_sensor': 'smart_home',
            'smart_light': 'smart_home',
            'pressure_sensor': 'industrial',
            'vibration_sensor': 'industrial',
            'heart_monitor': 'healthcare',
            'blood_pressure': 'healthcare',
            'air_quality': 'environmental',
            'water_sensor': 'environmental',
            'soil_sensor': 'environmental'
        }
    
    def start_traffic(self, duration=300):
        """Bắt đầu generate traffic"""
        self.running = True
        start_time = time.time()
        
        print(f"🚦 Starting IoT traffic simulation for {duration} seconds")
        print(f"📱 Devices: {list(self.device_patterns.keys())}")
        
        # Tạo thread cho mỗi device
        for device_name, pattern_name in self.device_patterns.items():
            try:
                host = self.net.get(device_name)
                if host:
                    thread = threading.Thread(
                        target=self._device_traffic_worker,
                        args=(host, pattern_name, start_time, duration)
                    )
                    thread.daemon = True
                    thread.start()
                    self.threads.append(thread)
                    print(f"  → {device_name}: {pattern_name} traffic")
                else:
                    print(f"  ❌ Device {device_name} not found in network")
            except Exception as e:
                print(f"  ❌ Error starting traffic for {device_name}: {e}")
        
        # Chờ kết thúc
        try:
            while time.time() - start_time < duration and self.running:
                time.sleep(1)
                
                # Hiển thị progress mỗi 30s
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0:
                    print(f"⏰ Traffic running: {int(elapsed)}/{duration}s")
                    
        except KeyboardInterrupt:
            print("\n🛑 Traffic generation interrupted")
        finally:
            self.stop_traffic()
    
    def _device_traffic_worker(self, host, pattern_name, start_time, duration):
        """Worker thread cho mỗi device"""
        pattern_config = self.traffic_patterns[pattern_name]
        
        while time.time() - start_time < duration and self.running:
            try:
                # Random interval và packet size
                interval = random.uniform(*pattern_config['interval'])
                size = random.randint(*pattern_config['size'])
                
                # Chọn destination ngẫu nhiên
                dest_ip = random.choice(pattern_config['destinations'])
                
                # Tạo traffic dựa trên protocol
                if pattern_config['protocol'] == 'UDP':
                    self._send_udp_traffic(host, dest_ip, size)
                else:
                    self._send_tcp_traffic(host, dest_ip, size)
                
                # Log traffic
                self._log_traffic(host.name, dest_ip, size, pattern_name)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"❌ Traffic error for {host.name}: {e}")
                break
    
    def _send_udp_traffic(self, host, dest_ip, size):
        """Gửi UDP traffic"""
        try:
            # Sử dụng ping để mô phỏng UDP traffic (đơn giản)
            # Trong thực tế có thể dùng iperf hoặc custom UDP client
            host.cmd(f'ping -c 1 -s {size} {dest_ip} > /dev/null 2>&1 &')
        except Exception as e:
            print(f"❌ UDP traffic error from {host.name}: {e}")
    
    def _send_tcp_traffic(self, host, dest_ip, size):
        """Gửi TCP traffic"""  
        try:
            # Sử dụng curl hoặc wget để mô phỏng TCP traffic
            # Giả lập gửi dữ liệu TCP
            host.cmd(f'curl -s -o /dev/null http://{dest_ip}:8080 --max-time 1 > /dev/null 2>&1 &')
        except Exception as e:
            print(f"❌ TCP traffic error from {host.name}: {e}")
    
    def _log_traffic(self, source, destination, size, pattern):
        """Log traffic ra file"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'destination': destination, 
            'size': size,
            'pattern': pattern
        }
        
        try:
            os.makedirs('results', exist_ok=True)
            with open('results/traffic_log.json', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"❌ Error logging traffic: {e}")
    
    def stop_traffic(self):
        """Dừng tất cả traffic"""
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)
        print("🛑 All traffic stopped")

def generate_ddos_attack(net, target_ip='10.0.1.10', duration=60):
    """Tạo DDoS attack scenario để test Q-learning"""
    print(f"🔥 Generating DDoS attack to {target_ip} for {duration} seconds")
    
    def attack_worker(host_name):
        try:
            host = net.get(host_name)
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Gửi nhiều packets liên tục
                for _ in range(5):  # 5 packets mỗi lần
                    host.cmd(f'ping -c 1 -W 1 {target_ip} > /dev/null 2>&1 &')
                time.sleep(0.1)  # 10 packets mỗi giây
                
        except Exception as e:
            print(f"❌ Attack error from {host_name}: {e}")
    
    # Sử dụng tất cả IoT devices để tấn công
    attackers = [
        'motion_sensor', 'temp_sensor', 'smart_light', 
        'pressure_sensor', 'vibration_sensor', 'heart_monitor',
        'blood_pressure', 'air_quality', 'water_sensor', 'soil_sensor'
    ]
    
    threads = []
    for attacker in attackers:
        try:
            if net.get(attacker):
                thread = threading.Thread(target=attack_worker, args=(attacker,))
                thread.daemon = True
                thread.start()
                threads.append(thread)
                print(f"  → {attacker} joining attack")
        except:
            pass
    
    # Chờ kết thúc attack
    print(f"⏰ DDoS attack running for {duration} seconds...")
    time.sleep(duration)
    print("🛑 DDoS attack stopped")

def main():
    """Test traffic generator"""
    print("🚦 IoT Traffic Generator - Standalone Test")
    
    # This would typically be called from the experiment runner
    print("✅ Traffic generator module loaded successfully")

if __name__ == "__main__":
    main()