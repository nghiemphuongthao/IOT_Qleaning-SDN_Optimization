import sys
import os
import time
import json

# Configure Python path for Mininet
sys.path.extend(['/usr/lib/python3/dist-packages', '/usr/local/lib/python3.8/dist-packages'])

try:
    from mininet.net import Mininet
    from mininet.node import Controller, RemoteController, OVSSwitch
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info, error
    from mininet.link import TCLink
    print("✅ Mininet imports successful")
except ImportError as e:
    print(f"❌ Mininet import error: {e}")
    sys.exit(1)

class IoTNetworkTopology:
    def __init__(self):
        self.net = None
        self.controller_ip = '172.20.0.10'  # Ryu container
        self.controller_port = 6633
        
    def create_topology(self):
        """Tạo topology mạng IoT hoàn chỉnh"""
        info('*** 🚀 Khởi tạo IoT SDN Network\n')
        
        try:
            # Khởi tạo Mininet với custom links
            self.net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)
            
            # Thêm Ryu SDN Controller
            info('*** Thêm SDN Controller\n')
            c0 = self.net.addController('c0',
                                      controller=RemoteController,
                                      ip=self.controller_ip,
                                      port=self.controller_port)
            
            # TẠO SWITCHES - 5 switches theo thiết kế
            info('***  Tạo switches\n')
            switches = {}
            for i in range(1, 6):
                switch_name = f's{i}'
                switches[switch_name] = self.net.addSwitch(switch_name)
                info(f'***   - {switch_name}\n')
            
            # TẠO HOSTS - Phân loại rõ ràng
            info('***  Tạo servers và gateway\n')
            
            # Core Infrastructure
            main_server = self.net.addHost('main_server', ip='10.0.1.10/24')
            backup_server = self.net.addHost('backup_server', ip='10.0.1.11/24')
            gateway = self.net.addHost('gateway', ip='10.0.1.1/24')
            
            # IoT Devices - Phân nhóm theo ứng dụng
            info('***  Tạo IoT devices\n')
            iot_devices = {}
            
            # Smart Home Devices
            iot_devices['motion_sensor'] = self.net.addHost('motion_sensor', ip='10.0.2.101/24')
            iot_devices['temp_sensor'] = self.net.addHost('temp_sensor', ip='10.0.2.102/24')
            iot_devices['smart_light'] = self.net.addHost('smart_light', ip='10.0.2.103/24')
            
            # Industrial IoT
            iot_devices['pressure_sensor'] = self.net.addHost('pressure_sensor', ip='10.0.3.104/24')
            iot_devices['vibration_sensor'] = self.net.addHost('vibration_sensor', ip='10.0.3.105/24')
            
            # Healthcare IoT
            iot_devices['heart_monitor'] = self.net.addHost('heart_monitor', ip='10.0.4.106/24')
            iot_devices['blood_pressure'] = self.net.addHost('blood_pressure', ip='10.0.4.107/24')
            
            # Environmental Monitoring
            iot_devices['air_quality'] = self.net.addHost('air_quality', ip='10.0.5.108/24')
            iot_devices['water_sensor'] = self.net.addHost('water_sensor', ip='10.0.5.109/24')
            iot_devices['soil_sensor'] = self.net.addHost('soil_sensor', ip='10.0.5.110/24')
            
            # KẾT NỐI MẠNG - Theo đúng topology thiết kế
            info('***  Thiết lập kết nối mạng\n')
            
            # Core infrastructure kết nối tới switch trung tâm S1
            self.net.addLink(main_server, switches['s1'])
            self.net.addLink(backup_server, switches['s1'])
            self.net.addLink(gateway, switches['s1'])
            info('***   - Servers & Gateway → s1\n')
            
            # Switch backbone - S1 kết nối tới S2-S5
            self.net.addLink(switches['s1'], switches['s2'])
            self.net.addLink(switches['s1'], switches['s3'])
            self.net.addLink(switches['s1'], switches['s4'])
            self.net.addLink(switches['s1'], switches['s5'])
            info('***   - s1 → s2,s3,s4,s5\n')
            
            # Kết nối IoT devices tới các edge switches
            # S2 - Smart Home
            self.net.addLink(switches['s2'], iot_devices['motion_sensor'])
            self.net.addLink(switches['s2'], iot_devices['temp_sensor'])
            
            # S3 - Smart Home & Additional
            self.net.addLink(switches['s3'], iot_devices['smart_light'])
            self.net.addLink(switches['s3'], iot_devices['air_quality'])
            
            # S4 - Industrial IoT
            self.net.addLink(switches['s4'], iot_devices['pressure_sensor'])
            self.net.addLink(switches['s4'], iot_devices['vibration_sensor'])
            
            # S5 - Healthcare & Environmental
            self.net.addLink(switches['s5'], iot_devices['heart_monitor'])
            self.net.addLink(switches['s5'], iot_devices['blood_pressure'])
            self.net.addLink(switches['s5'], iot_devices['water_sensor'])
            self.net.addLink(switches['s5'], iot_devices['soil_sensor'])
            
            info('***   - IoT devices connected to edge switches\n')
            
            return self.net
            
        except Exception as e:
            error(f'***  Lỗi khi tạo topology: {e}\n')
            return None
    
    def start_network(self):
        """Khởi động toàn bộ mạng"""
        if not self.net:
            error('*** Network chưa được tạo\n')
            return False
            
        info('*** Building network\n')
        self.net.build()
        
        info('***  Starting controller\n')
        self.net.get('c0').start()
        
        info('***  Starting switches\n')
        for switch in self.net.switches:
            switch.start([self.net.controllers[0]])
            info(f'***   - {switch.name} started\n')
        
        info('***  Testing network connectivity\n')
        self.test_connectivity()
        
        info('***  Network started successfully!\n')
        return True
    
    def test_connectivity(self):
        """Kiểm tra kết nối cơ bản"""
        info('*** Testing basic connectivity\n')
        try:
            main_server = self.net.get('main_server')
            gateway = self.net.get('gateway')
            
            # Test ping từ server tới gateway
            result = main_server.cmd('ping -c 3 %s' % gateway.IP())
            if '3 received' in result:
                info('*** Gateway connectivity: OK\n')
            else:
                info('*** Gateway connectivity: FAILED\n')
                
            # Test connectivity từ IoT device
            motion_sensor = self.net.get('motion_sensor')
            result = motion_sensor.cmd('ping -c 2 %s' % main_server.IP())
            if '2 received' in result:
                info('***  IoT to Server connectivity: OK\n')
            else:
                info('*** IoT to Server connectivity: FAILED\n')
                
        except Exception as e:
            error(f'*** Connectivity test error: {e}\n')
    
    def save_topology_info(self):
        """Lưu thông tin topology để sử dụng cho Q-learning"""
        try:
            topology_info = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'switches': [s.name for s in self.net.switches],
                'hosts': [h.name for h in self.net.hosts],
                'links': [],
                'ip_mapping': {},
                'controller': {
                    'ip': self.controller_ip,
                    'port': self.controller_port
                }
            }
            
            for host in self.net.hosts:
                topology_info['ip_mapping'][host.name] = host.IP()
            
            # Đảm bảo thư mục results tồn tại
            os.makedirs('results', exist_ok=True)
            
            with open('results/topology_info.json', 'w') as f:
                json.dump(topology_info, f, indent=2)
                
            info('*** Topology info saved to results/topology_info.json\n')
            
        except Exception as e:
            error(f'*** Error saving topology info: {e}\n')
    
    def stop_network(self):
        """Dừng mạng"""
        if self.net:
            info('***  Stopping network\n')
            self.net.stop()

def main():
    """Main function để chạy topology"""
    setLogLevel('info')
    
    print("=" * 60)
    print(" IoT SDN NETWORK TOPOLOGY - ĐỒ ÁN TỐT NGHIỆP")
    print("=" * 60)
    
    # Tạo và khởi động topology
    topology = IoTNetworkTopology()
    net = topology.create_topology()
    
    if net and topology.start_network():
        topology.save_topology_info()
        
        print("\nTopology started successfully!")
        print("Network is running...")
        print("Use 'pingall' in Mininet CLI to test connectivity")
        print("Press Ctrl+C to stop the network")
        
        # Giữ mạng chạy và cung cấp CLI
        try:
            CLI(net)
        except KeyboardInterrupt:
            print("\n*** CLI interrupted by user")
        finally:
            topology.stop_network()
    else:
        error('*** Failed to start network\n')

if __name__ == '__main__':
    main()