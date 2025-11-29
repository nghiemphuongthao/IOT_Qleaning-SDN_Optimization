import time
import random
import logging
import subprocess
from scapy.all import IP, ICMP, TCP, UDP, Ether, sendp, conf
from scapy.all import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TrafficGenerator:
    def __init__(self):
        self.hosts = [
            '10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4',
            '10.0.0.5', '10.0.0.6', '10.0.0.7', '10.0.0.8'
        ]
        self.find_available_interface()
    
    def find_available_interface(self):
        """Tìm interface có sẵn để gửi traffic"""
        try:
            # Thử các interface phổ biến
            test_interfaces = ['eth0', 'eth1', 'ens33', 'ens32', 'eno1', 'wlan0']
            for iface in test_interfaces:
                try:
                    # Kiểm tra interface có tồn tại không
                    result = subprocess.run(['ip', 'link', 'show', iface], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        self.interface = iface
                        logging.info(f"Using interface: {iface}")
                        return
                except:
                    continue
            
            # Nếu không tìm thấy, sử dụng interface mặc định
            self.interface = conf.iface
            logging.info(f"Using default interface: {self.interface}")
        except:
            self.interface = None
            logging.warning("No interface found, traffic generation may fail")
    
    def generate_icmp_traffic(self, count=10):
        logging.info(f"Generating {count} ICMP packets")
        success_count = 0
        for i in range(count):
            try:
                src = random.choice(self.hosts)
                dst = random.choice([h for h in self.hosts if h != src])
                
                packet = Ether()/IP(src=src, dst=dst)/ICMP()
                if self.interface:
                    sendp(packet, iface=self.interface, verbose=False)
                else:
                    sendp(packet, verbose=False)
                success_count += 1
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Failed to send ICMP packet: {e}")
        
        logging.info(f"Successfully sent {success_count}/{count} ICMP packets")
    
    def generate_tcp_traffic(self, count=5):
        logging.info(f"Generating {count} TCP packets")
        success_count = 0
        for i in range(count):
            try:
                src = random.choice(self.hosts)
                dst = random.choice([h for h in self.hosts if h != src])
                sport = random.randint(1024, 65535)
                dport = random.randint(1, 1000)
                
                packet = Ether()/IP(src=src, dst=dst)/TCP(sport=sport, dport=dport)
                if self.interface:
                    sendp(packet, iface=self.interface, verbose=False)
                else:
                    sendp(packet, verbose=False)
                success_count += 1
                time.sleep(0.2)
            except Exception as e:
                logging.error(f"Failed to send TCP packet: {e}")
        
        logging.info(f"Successfully sent {success_count}/{count} TCP packets")
    
    def run(self):
        logging.info("Starting traffic generator")
        try:
            while True:
                self.generate_icmp_traffic(5)  # Giảm số lượng packet để test
                time.sleep(2)
                self.generate_tcp_traffic(3)   # Giảm số lượng packet để test
                time.sleep(3)
        except KeyboardInterrupt:
            logging.info("Traffic generator stopped")
        except Exception as e:
            logging.error(f"Traffic generator error: {e}")

if __name__ == "__main__":
    generator = TrafficGenerator()
    generator.run()