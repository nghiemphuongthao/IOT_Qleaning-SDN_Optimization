#!/usr/bin/env python3

import json
import requests
import statistics
from datetime import datetime

class PerformanceComparator:
    def __init__(self):
        self.baseline_url = os.getenv('RYU_BASELINE_URL', 'http://172.20.0.10:8080')
        self.sdn_url = os.getenv('RYU_SDN_URL', 'http://172.20.0.11:8080')
        self.sdn_qlearning_url = os.getenv('RYU_SDN_QLEARNING_URL', 'http://172.20.0.12:8080')
        
    def collect_metrics(self):
        metrics = {}
        
        for case, url in [('baseline', self.baseline_url),
                         ('sdn', self.sdn_url), 
                         ('sdn_qlearning', self.sdn_qlearning_url)]:
            
            try:
                # Get switch statistics
                switches = requests.get(f"{url}/stats/switches").json()
                flow_stats = requests.get(f"{url}/stats/flow/1").json()
                port_stats = requests.get(f"{url}/stats/port/1").json()
                
                metrics[case] = {
                    'switches_count': len(switches.get('switches', [])),
                    'flow_entries': self.count_flow_entries(flow_stats),
                    'throughput': self.calculate_throughput(port_stats),
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"Error collecting metrics for {case}: {e}")
                metrics[case] = {}
                
        return metrics
    
    def generate_report(self, metrics):
        report = {
            'comparison_timestamp': datetime.now().isoformat(),
            'cases': metrics,
            'improvements': self.calculate_improvements(metrics)
        }
        
        # Save report
        with open('/shared/comparison_report.json', 'w') as f:
            json.dump(report, f, indent=2)
            
        return report
    
    def calculate_improvements(self, metrics):
        improvements = {}
        
        baseline_flows = metrics.get('baseline', {}).get('flow_entries', 0)
        sdn_flows = metrics.get('sdn', {}).get('flow_entries', 0)
        sdn_qlearning_flows = metrics.get('sdn_qlearning', {}).get('flow_entries', 0)
        
        if baseline_flows > 0:
            improvements['sdn_vs_baseline'] = {
                'flow_reduction_percent': ((baseline_flows - sdn_flows) / baseline_flows) * 100,
                'efficiency_gain': sdn_flows / baseline_flows
            }
            
        if sdn_flows > 0:
            improvements['qlearning_vs_sdn'] = {
                'optimization_improvement': ((sdn_qlearning_flows - sdn_flows) / sdn_flows) * 100
            }
            
        return improvements

if __name__ == '__main__':
    comparator = PerformanceComparator()
    metrics = comparator.collect_metrics()
    report = comparator.generate_report(metrics)
    
    print("=== SDN Performance Comparison Report ===")
    print(json.dumps(report, indent=2))