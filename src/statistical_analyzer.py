import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

class StatisticalAnalyzer:
    def __init__(self, results_path):
        self.results_path = results_path

    def load_data(self):
        # Load dữ liệu từ các file kết quả
        pass

    def perform_t_test(self, data1, data2):
        # Thực hiện t-test để so sánh hai mẫu
        t_stat, p_value = stats.ttest_ind(data1, data2)
        return t_stat, p_value

    def perform_anova(self, data_list):
        # Thực hiện ANOVA để so sánh nhiều mẫu
        f_stat, p_value = stats.f_oneway(*data_list)
        return f_stat, p_value

    def generate_report(self):
        # Tạo báo cáo thống kê
        report = {
            'mean': np.mean(self.data),
            'std': np.std(self.data),
            'min': np.min(self.data),
            'max': np.max(self.data)
        }
        return report

    def plot_metrics(self, metrics_list, labels, title):
        # Vẽ biểu đồ so sánh các metrics
        for i, metrics in enumerate(metrics_list):
            plt.plot(metrics, label=labels[i])
        plt.title(title)
        plt.legend()
        plt.savefig(f'{self.results_path}/{title}.png')
        plt.close()