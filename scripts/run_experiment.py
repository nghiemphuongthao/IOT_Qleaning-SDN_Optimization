#!/usr/bin/env python3
"""
Main Experiment Runner - Điều phối toàn bộ thí nghiệm
"""

import os
import time
import subprocess
import sys
import json
from datetime import datetime

class ExperimentRunner:
    def __init__(self):
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f"results/experiment_{self.experiment_id}"
        
    def setup_environment(self):
        """Thiết lập môi trường thí nghiệm"""
        print("🔧 Setting up experiment environment...")
        
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Khởi động Docker environment
        result = subprocess.run(["docker-compose", "up", "-d"], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Docker-compose error: {result.stderr}")
            return False
            
        print("✅ Docker environment started")
        time.sleep(15)  # Chờ các service khởi động
        return True
    
    def run_baseline_experiment(self, duration=300):
        """Chạy baseline experiment (không optimization)"""
        print("\n🔬 Running BASELINE Experiment")
        
        # Khởi động Mininet topology
        self._start_mininet_topology()
        time.sleep(10)
        
        # Chạy traffic generation
        self._start_traffic_generation(duration)
        
        # Chờ kết thúc
        print(f"⏳ Running baseline for {duration} seconds...")
        time.sleep(duration)
        
        # Thu thập kết quả
        self._collect_results("baseline")
        
        print("✅ Baseline experiment completed")
    
    def run_sdn_experiment(self, duration=300):
        """Chạy SDN experiment (chỉ Ryu controller)"""
        print("\n🎮 Running SDN Experiment")
        
        # Ryu controller đã chạy trong Docker
        self._start_mininet_topology()
        time.sleep(10)
        
        # Chạy traffic generation
        self._start_traffic_generation(duration)
        
        # Chờ kết thúc
        print(f"⏳ Running SDN experiment for {duration} seconds...")
        time.sleep(duration)
        
        # Thu thập kết quả
        self._collect_results("ryu_sdn")
        
        print("✅ SDN experiment completed")
    
    def run_qlearning_experiment(self, duration=600):
        """Chạy Q-learning experiment"""
        print("\n🧠 Running Q-LEARNING Experiment")
        
        # Ryu controller và Q-learning agent đã chạy trong Docker
        self._start_mininet_topology()
        time.sleep(10)
        
        # Chạy traffic generation
        self._start_traffic_generation(duration)
        
        # Chờ Q-learning training
        print(f"⏳ Running Q-learning experiment for {duration} seconds...")
        time.sleep(duration)
        
        # Thu thập kết quả
        self._collect_results("qlearning_optimized")
        
        print("✅ Q-learning experiment completed")
    
    def _start_mininet_topology(self):
        """Khởi động Mininet topology"""
        print("🔗 Starting Mininet topology...")
        
        try:
            subprocess.run([
                "docker", "exec", "-d", "mininet-topology",
                "python3", "/app/src/mininet_topology.py"
            ], check=True)
            time.sleep(10)
            print("✅ Mininet topology started")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting Mininet: {e}")
    
    def _start_traffic_generation(self, duration):
        """Khởi động traffic generation"""
        print("🚦 Starting traffic generation...")
        
        try:
            subprocess.run([
                "docker", "exec", "-d", "mininet-topology",
                "python3", "/app/src/traffic_generator.py"
            ], check=True)
            print("✅ Traffic generation started")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error starting traffic generation: {e}")
    
    def _collect_results(self, experiment_type):
        """Thu thập kết quả từ containers"""
        print(f"📦 Collecting {experiment_type} results...")
        
        try:
            # Tạo thư mục kết quả
            target_dir = f"{self.results_dir}/{experiment_type}"
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy kết quả từ các containers
            containers = ["mininet-topology", "qlearning-agent", "ryu-controller"]
            for container in containers:
                try:
                    subprocess.run([
                        "docker", "cp",
                        f"{container}:/app/results/.",
                        target_dir
                    ], check=False)  # Không fail nếu không có results
                except:
                    pass
            
            print(f"✅ {experiment_type} results collected")
            
        except Exception as e:
            print(f"❌ Error collecting {experiment_type} results: {e}")
    
    def cleanup(self):
        """Dọn dẹp environment"""
        print("🧹 Cleaning up environment...")
        subprocess.run(["docker-compose", "down"], capture_output=True)
        print("✅ Environment cleaned up")
    
    def run_complete_experiment(self):
        """Chạy toàn bộ thí nghiệm"""
        print("=" * 60)
        print("🎯 IOT SDN Q-LEARNING - COMPLETE EXPERIMENT")
        print(f"📝 Experiment ID: {self.experiment_id}")
        print("=" * 60)
        
        try:
            # Thiết lập environment
            if not self.setup_environment():
                return False
            
            # Chạy các thí nghiệm
            self.run_baseline_experiment(300)    # 5 phút
            self.run_sdn_experiment(300)         # 5 phút  
            self.run_qlearning_experiment(600)   # 10 phút
            
            print("\n🎉 ALL EXPERIMENTS COMPLETED SUCCESSFULLY!")
            print(f"📊 Results available in: {self.results_dir}")
            
            # Tạo báo cáo
            self.generate_reports()
            
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Experiment interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Experiment error: {e}")
            return False
        finally:
            self.cleanup()
    
    def generate_reports(self):
        """Tạo báo cáo so sánh"""
        print("\n📄 Generating comparison reports...")
        
        try:
            # Chạy script tạo báo cáo
            subprocess.run([
                "python3", "scripts/generate_reports.py",
                "--input", self.results_dir,
                "--output", f"{self.results_dir}/comparison"
            ], check=True)
            
            print("✅ Reports generated successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error generating reports: {e}")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Chạy thí nghiệm cụ thể
        experiment_type = sys.argv[1]
        runner = ExperimentRunner()
        
        if experiment_type == "baseline":
            runner.run_baseline_experiment()
        elif experiment_type == "sdn":
            runner.run_sdn_experiment()
        elif experiment_type == "qlearning":
            runner.run_qlearning_experiment()
        else:
            print("Usage: python run_experiment.py [baseline|sdn|qlearning|all]")
    else:
        # Chạy toàn bộ thí nghiệm
        runner = ExperimentRunner()
        success = runner.run_complete_experiment()
        
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()