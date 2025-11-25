#!/usr/bin/env python3
"""
Main Experiment Runner - Điều phối toàn bộ thí nghiệm
"""

import os
import time
import subprocess
import sys
from datetime import datetime


class ExperimentRunner:
    def __init__(self):
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f"results/experiment_{self.experiment_id}"
        self.docker_cmd = self._detect_docker_compose()

    # ---------------------------
    # Utility methods
    # ---------------------------
    def _detect_docker_compose(self):
        """Detect whether to use docker-compose or docker compose"""
        if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
            return ["docker", "compose"]
        elif subprocess.run(["docker-compose", "version"], capture_output=True).returncode == 0:
            return ["docker-compose"]
        else:
            raise RuntimeError("Docker Compose not found")
        
    def _run_subprocess(self, cmd, check=True, capture_output=False):
        """Wrapper for subprocess.run with error handling"""
        try:
            return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {' '.join(cmd)}\n{e.stderr if e.stderr else e}")
            return None

    # ---------------------------
    # Environment setup & cleanup
    # ---------------------------
    def setup_environment(self):
        print("🔧 Setting up experiment environment...")
        for d in [self.results_dir, "logs"]:
            os.makedirs(d, exist_ok=True)

        if not self._run_subprocess(self.docker_cmd + ["up", "-d"]):
            return False

        print("✅ Docker environment started")
        time.sleep(15)
        return True

    def cleanup(self):
        """Dọn dẹp environment"""
        print("🧹 Cleaning up environment...")
        self._run_subprocess([self.docker_cmd, "down"], check=False, capture_output=True)
        print("✅ Environment cleaned up")

    # ---------------------------
    # Experiment runners
    # ---------------------------
    def _run_experiment(self, name, duration):
        """Generic experiment runner"""
        print(f"\n🚀 Running {name.upper()} Experiment")

        self._start_mininet_topology()
        time.sleep(10)

        self._start_traffic_generation(duration)

        print(f"⏳ Running {name} experiment for {duration} seconds...")
        time.sleep(duration)

        self._collect_results(name)
        print(f"✅ {name.capitalize()} experiment completed")

    def run_baseline_experiment(self, duration=300):
        self._run_experiment("baseline", duration)

    def run_sdn_experiment(self, duration=300):
        self._run_experiment("ryu_sdn", duration)

    def run_qlearning_experiment(self, duration=600):
        self._run_experiment("qlearning_optimized", duration)

    # ---------------------------
    # Helpers
    # ---------------------------
    def _start_mininet_topology(self):
        print("🔗 Starting Mininet topology...")
        if self._run_subprocess([
            "docker", "exec", "-d", "mininet-topology",
            "python3", "/app/src/mininet_topology.py"
        ]):
            time.sleep(10)
            print("✅ Mininet topology started")

    def _start_traffic_generation(self, duration):
        print("🚦 Starting traffic generation...")
        if self._run_subprocess([
            "docker", "exec", "-d", "mininet-topology",
            "python3", "/app/src/traffic_generator.py"
        ]):
            print("✅ Traffic generation started")

    def _collect_results(self, experiment_type):
        print(f"📦 Collecting {experiment_type} results...")
        target_dir = f"{self.results_dir}/{experiment_type}"
        os.makedirs(target_dir, exist_ok=True)

        for container in ["mininet-topology", "qlearning-agent", "ryu-controller"]:
            self._run_subprocess([
                "docker", "cp",
                f"{container}:/app/results/.",
                target_dir
            ], check=False)

        print(f"✅ {experiment_type} results collected")

    def generate_reports(self):
        print("\n📄 Generating comparison reports...")
        if self._run_subprocess([
            "python3", "scripts/generate_reports.py",
            "--input", self.results_dir,
            "--output", f"{self.results_dir}/comparison"
        ]):
            print("✅ Reports generated successfully")

    # ---------------------------
    # Complete experiment
    # ---------------------------
    def run_complete_experiment(self):
        print("=" * 60)
        print("🎯 IOT SDN Q-LEARNING - COMPLETE EXPERIMENT")
        print(f"📝 Experiment ID: {self.experiment_id}")
        print("=" * 60)

        try:
            if not self.setup_environment():
                return False

            self.run_baseline_experiment(300)
            self.run_sdn_experiment(300)
            self.run_qlearning_experiment(600)

            print("\n🎉 ALL EXPERIMENTS COMPLETED SUCCESSFULLY!")
            print(f"📊 Results available in: {self.results_dir}")

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


def main():
    runner = ExperimentRunner()
    if len(sys.argv) > 1:
        experiment_type = sys.argv[1]
        if experiment_type == "baseline":
            runner.run_baseline_experiment()
        elif experiment_type == "sdn":
            runner.run_sdn_experiment()
        elif experiment_type == "qlearning":
            runner.run_qlearning_experiment()
        elif experiment_type == "all":
            success = runner.run_complete_experiment()
            sys.exit(0 if success else 1)
        else:
            print("Usage: python run_experiment.py [baseline|sdn|qlearning|all]")
    else:
        success = runner.run_complete_experiment()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
