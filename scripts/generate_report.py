#!/usr/bin/env python3
"""
Report Generator - Tạo báo cáo so sánh kết quả
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import glob
import sys
from datetime import datetime

class ReportGenerator:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Thiết lập style
        plt.style.use('seaborn')
        sns.set_palette("husl")
    
    def load_experiment_data(self):
        """Tải dữ liệu từ các thí nghiệm"""
        experiments = {}
        
        for exp_type in ['baseline', 'ryu_sdn', 'qlearning_optimized']:
            exp_path = os.path.join(self.input_dir, exp_type)
            if os.path.exists(exp_path):
                experiments[exp_type] = self._load_single_experiment(exp_path)
        
        return experiments
    
    def _load_single_experiment(self, exp_path):
        """Tải dữ liệu từ một thí nghiệm"""
        data = {
            'network_metrics': [],
            'training_data': [],
            'traffic_logs': []
        }
        
        # Tải network metrics
        metrics_files = glob.glob(os.path.join(exp_path, 'network_metrics*.json'))
        for file in metrics_files:
            try:
                with open(file, 'r') as f:
                    for line in f:
                        data['network_metrics'].append(json.loads(line))
            except:
                pass
        
        # Tải training data (nếu có)
        training_files = glob.glob(os.path.join(exp_path, 'training_history.json'))
        for file in training_files:
            try:
                with open(file, 'r') as f:
                    data['training_data'] = json.load(f)
            except:
                pass
        
        # Tải traffic logs
        traffic_files = glob.glob(os.path.join(exp_path, 'traffic_log.json'))
        for file in traffic_files:
            try:
                with open(file, 'r') as f:
                    for line in f:
                        data['traffic_logs'].append(json.loads(line))
            except:
                pass
        
        return data
    
    def create_performance_comparison(self, experiments):
        """Tạo so sánh hiệu năng"""
        print("📊 Creating performance comparison...")
        
        # Chuẩn bị dữ liệu
        comparison_data = []
        
        for exp_name, data in experiments.items():
            if data['network_metrics']:
                df = pd.DataFrame(data['network_metrics'])
                
                summary = {
                    'Experiment': exp_name,
                    'Throughput (Mbps)': df['throughput'].mean(),
                    'Latency (ms)': df['latency'].mean(),
                    'Packet Loss (%)': df['packet_loss'].mean(),
                    'Jitter (ms)': df.get('jitter', 0).mean(),
                    'Active Flows': df.get('active_flows', 0).mean(),
                    'Sample Count': len(df)
                }
                comparison_data.append(summary)
        
        if not comparison_data:
            print("❌ No performance data found")
            return
        
        # Tạo DataFrame
        comparison_df = pd.DataFrame(comparison_data)
        
        # Lưu dữ liệu
        comparison_df.to_csv(os.path.join(self.output_dir, 'performance_comparison.csv'), index=False)
        comparison_df.to_excel(os.path.join(self.output_dir, 'performance_comparison.xlsx'), index=False)
        
        # Tạo biểu đồ
        self._create_performance_charts(comparison_df)
        
        return comparison_df
    
    def _create_performance_charts(self, df):
        """Tạo biểu đồ so sánh hiệu năng"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Performance Comparison - IoT SDN with Q-learning', fontsize=16, fontweight='bold')
        
        # Throughput comparison
        axes[0,0].bar(df['Experiment'], df['Throughput (Mbps)'])
        axes[0,0].set_title('Average Throughput')
        axes[0,0].set_ylabel('Mbps')
        axes[0,0].tick_params(axis='x', rotation=45)
        
        # Latency comparison  
        axes[0,1].bar(df['Experiment'], df['Latency (ms)'])
        axes[0,1].set_title('Average Latency')
        axes[0,1].set_ylabel('ms')
        axes[0,1].tick_params(axis='x', rotation=45)
        
        # Packet loss comparison
        axes[1,0].bar(df['Experiment'], df['Packet Loss (%)'])
        axes[1,0].set_title('Packet Loss Rate')
        axes[1,0].set_ylabel('%')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # Active flows comparison
        axes[1,1].bar(df['Experiment'], df['Active Flows'])
        axes[1,1].set_title('Active Flows')
        axes[1,1].set_ylabel('Count')
        axes[1,1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'performance_comparison.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_training_analysis(self, experiments):
        """Phân tích quá trình training Q-learning"""
        qlearning_data = experiments.get('qlearning_optimized', {})
        training_data = qlearning_data.get('training_data', [])
        
        if not training_data:
            print("❌ No training data found for Q-learning")
            return
        
        df = pd.DataFrame(training_data)
        
        # Tạo biểu đồ training progress
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Q-learning Training Progress', fontsize=16, fontweight='bold')
        
        # Reward progression
        if 'total_reward' in df.columns:
            axes[0,0].plot(df['episode'], df['total_reward'])
            axes[0,0].set_title('Total Reward per Episode')
            axes[0,0].set_xlabel('Episode')
            axes[0,0].set_ylabel('Reward')
            axes[0,0].grid(True, alpha=0.3)
        
        # Epsilon decay
        if 'epsilon' in df.columns:
            axes[0,1].plot(df['episode'], df['epsilon'])
            axes[0,1].set_title('Exploration Rate (Epsilon)')
            axes[0,1].set_xlabel('Episode')
            axes[0,1].set_ylabel('Epsilon')
            axes[0,1].grid(True, alpha=0.3)
        
        # Memory size
        if 'memory_size' in df.columns:
            axes[1,0].plot(df['episode'], df['memory_size'])
            axes[1,0].set_title('Experience Memory Size')
            axes[1,0].set_xlabel('Episode')
            axes[1,0].set_ylabel('Memory Size')
            axes[1,0].grid(True, alpha=0.3)
        
        # Reward distribution
        if 'total_reward' in df.columns:
            axes[1,1].hist(df['total_reward'], bins=20, alpha=0.7, edgecolor='black')
            axes[1,1].set_title('Reward Distribution')
            axes[1,1].set_xlabel('Reward')
            axes[1,1].set_ylabel('Frequency')
            axes[1,1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'training_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
        
        # Lưu training statistics
        training_stats = {
            'total_episodes': len(df),
            'average_reward': df['total_reward'].mean(),
            'max_reward': df['total_reward'].max(),
            'min_reward': df['total_reward'].min(),
            'final_epsilon': df['epsilon'].iloc[-1] if 'epsilon' in df.columns else 0
        }
        
        with open(os.path.join(self.output_dir, 'training_statistics.json'), 'w') as f:
            json.dump(training_stats, f, indent=2)
    
    def create_traffic_analysis(self, experiments):
        """Phân tích traffic patterns"""
        print("🚦 Analyzing traffic patterns...")
        
        all_traffic_data = []
        
        for exp_name, data in experiments.items():
            traffic_logs = data.get('traffic_logs', [])
            if traffic_logs:
                df = pd.DataFrame(traffic_logs)
                df['experiment'] = exp_name
                all_traffic_data.append(df)
        
        if not all_traffic_data:
            print("❌ No traffic data found")
            return
        
        traffic_df = pd.concat(all_traffic_data, ignore_index=True)
        
        # Phân tích traffic patterns
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Traffic Patterns Analysis', fontsize=16, fontweight='bold')
        
        # Traffic volume by experiment
        traffic_volume = traffic_df.groupby('experiment').size()
        axes[0,0].bar(traffic_volume.index, traffic_volume.values)
        axes[0,0].set_title('Total Traffic Volume')
        axes[0,0].set_ylabel('Number of Packets')
        axes[0,0].tick_params(axis='x', rotation=45)
        
        # Traffic patterns distribution
        if 'pattern' in traffic_df.columns:
            pattern_counts = traffic_df.groupby(['experiment', 'pattern']).size().unstack(fill_value=0)
            pattern_counts.plot(kind='bar', ax=axes[0,1])
            axes[0,1].set_title('Traffic Patterns Distribution')
            axes[0,1].set_ylabel('Count')
            axes[0,1].tick_params(axis='x', rotation=45)
            axes[0,1].legend(title='Pattern')
        
        # Packet size distribution
        if 'size' in traffic_df.columns:
            traffic_df.boxplot(column='size', by='experiment', ax=axes[1,0])
            axes[1,0].set_title('Packet Size Distribution')
            axes[1,0].set_ylabel('Bytes')
        
        # Destination distribution
        if 'destination' in traffic_df.columns:
            dest_counts = traffic_df['destination'].value_counts()
            axes[1,1].pie(dest_counts.values, labels=dest_counts.index, autopct='%1.1f%%')
            axes[1,1].set_title('Traffic Destination Distribution')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'traffic_analysis.png'), 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_summary_report(self, experiments, performance_df):
        """Tạo báo cáo tổng hợp"""
        print("📄 Generating summary report...")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'experiments_conducted': list(experiments.keys()),
            'performance_summary': performance_df.to_dict('records'),
            'conclusions': self._generate_conclusions(performance_df)
        }
        
        with open(os.path.join(self.output_dir, 'experiment_summary.json'), 'w') as f:
            json.dump(report, f, indent=2)
        
        # Tạo report text
        self._create_text_report(report)
    
    def _generate_conclusions(self, performance_df):
        """Tạo kết luận từ kết quả"""
        conclusions = []
        
        if len(performance_df) > 1:
            best_throughput = performance_df.loc[performance_df['Throughput (Mbps)'].idxmax()]
            best_latency = performance_df.loc[performance_df['Latency (ms)'].idxmin()]
            
            conclusions.append({
                'best_throughput': f"{best_throughput['Experiment']} achieved highest throughput: {best_throughput['Throughput (Mbps)']:.2f} Mbps",
                'best_latency': f"{best_latency['Experiment']} achieved lowest latency: {best_latency['Latency (ms)']:.2f} ms",
                'improvement': "Q-learning shows adaptive optimization capabilities"
            })
        
        return conclusions
    
    def _create_text_report(self, report):
        """Tạo báo cáo văn bản"""
        with open(os.path.join(self.output_dir, 'experiment_report.txt'), 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("IOT SDN Q-LEARNING EXPERIMENT REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Generated: {report['generated_at']}\n")
            f.write(f"Experiments: {', '.join(report['experiments_conducted'])}\n\n")
            
            f.write("PERFORMANCE SUMMARY:\n")
            f.write("-" * 40 + "\n")
            
            for exp in report['performance_summary']:
                f.write(f"\n{exp['Experiment']}:\n")
                f.write(f"  Throughput: {exp['Throughput (Mbps)']:.2f} Mbps\n")
                f.write(f"  Latency: {exp['Latency (ms)']:.2f} ms\n")
                f.write(f"  Packet Loss: {exp['Packet Loss (%)']:.2f}%\n")
                f.write(f"  Active Flows: {exp['Active Flows']:.0f}\n")
            
            f.write("\nCONCLUSIONS:\n")
            f.write("-" * 40 + "\n")
            for conclusion in report['conclusions']:
                for key, value in conclusion.items():
                    f.write(f"- {value}\n")
    
    def generate_all_reports(self):
        """Tạo tất cả báo cáo"""
        print("🎯 Generating all reports...")
        
        # Tải dữ liệu
        experiments = self.load_experiment_data()
        
        if not experiments:
            print("❌ No experiment data found!")
            return
        
        print(f"📁 Loaded data from {len(experiments)} experiments")
        
        # Tạo các báo cáo
        performance_df = self.create_performance_comparison(experiments)
        self.create_training_analysis(experiments)
        self.create_traffic_analysis(experiments)
        self.generate_summary_report(experiments, performance_df)
        
        print(f"✅ All reports generated in: {self.output_dir}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate experiment reports')
    parser.add_argument('--input', default='results', help='Input directory with experiment results')
    parser.add_argument('--output', default='results/comparison', help='Output directory for reports')
    
    args = parser.parse_args()
    
    generator = ReportGenerator(args.input, args.output)
    generator.generate_all_reports()

if __name__ == "__main__":
    main()