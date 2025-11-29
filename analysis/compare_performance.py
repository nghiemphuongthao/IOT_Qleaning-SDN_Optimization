import numpy as np
import matplotlib.pyplot as plt
import json

def compare_routing_strategies():
    """So sánh các chiến lược routing khác nhau"""
    
    # Dữ liệu mẫu - trong thực tế cần thu thập từ experiments
    strategies = ['Q-Learning', 'Shortest Path', 'Random', 'Load Balancing']
    
    # Các metrics giả định (cần thay bằng dữ liệu thực)
    latency = [45.2, 52.1, 78.3, 48.7]  # ms
    throughput = [980, 920, 650, 940]    # Mbps
    packet_loss = [0.2, 0.5, 2.1, 0.4]   # %
    convergence_time = [120, 5, 0, 30]   # seconds
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # Biểu đồ latency
    axes[0, 0].bar(strategies, latency, color=['green', 'blue', 'red', 'orange'])
    axes[0, 0].set_title('So sánh Độ trễ (Latency)')
    axes[0, 0].set_ylabel('Latency (ms)')
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # Biểu đồ throughput
    axes[0, 1].bar(strategies, throughput, color=['green', 'blue', 'red', 'orange'])
    axes[0, 1].set_title('So sánh Băng thông (Throughput)')
    axes[0, 1].set_ylabel('Throughput (Mbps)')
    axes[0, 1].tick_params(axis='x', rotation=45)
    
    # Biểu đồ packet loss
    axes[1, 0].bar(strategies, packet_loss, color=['green', 'blue', 'red', 'orange'])
    axes[1, 0].set_title('So sánh Tỉ lệ mất gói (Packet Loss)')
    axes[1, 0].set_ylabel('Packet Loss (%)')
    axes[1, 0].tick_params(axis='x', rotation=45)
    
    # Biểu đồ convergence time
    axes[1, 1].bar(strategies, convergence_time, color=['green', 'blue', 'red', 'orange'])
    axes[1, 1].set_title('So sánh Thời gian hội tụ')
    axes[1, 1].set_ylabel('Thời gian (giây)')
    axes[1, 1].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('/shared/strategy_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Tính điểm tổng thể
    scores = {
        'Q-Learning': calculate_score(latency[0], throughput[0], packet_loss[0], convergence_time[0]),
        'Shortest Path': calculate_score(latency[1], throughput[1], packet_loss[1], convergence_time[1]),
        'Random': calculate_score(latency[2], throughput[2], packet_loss[2], convergence_time[2]),
        'Load Balancing': calculate_score(latency[3], throughput[3], packet_loss[3], convergence_time[3])
    }
    
    print("=== ĐIỂM ĐÁNH GIÁ CHIẾN LƯỢC ===")
    for strategy, score in scores.items():
        print(f"{strategy}: {score:.2f}/100")

def calculate_score(latency, throughput, packet_loss, convergence_time):
    """Tính điểm tổng hợp cho chiến lược"""
    latency_score = max(0, 100 - latency * 2)  # Latency càng thấp càng tốt
    throughput_score = min(100, throughput / 10)  # Throughput càng cao càng tốt
    loss_score = max(0, 100 - packet_loss * 50)  # Packet loss càng thấp càng tốt
    convergence_score = max(0, 100 - convergence_time / 2)  # Hội tụ càng nhanh càng tốt
    
    total_score = (latency_score * 0.3 + throughput_score * 0.3 + 
                   loss_score * 0.2 + convergence_score * 0.2)
    return total_score

if __name__ == "__main__":
    compare_routing_strategies()