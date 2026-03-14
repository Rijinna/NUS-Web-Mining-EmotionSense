import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, peak_prominences
import json
import argparse
from datetime import timedelta
import os

# ======= 配置区 =======
DEFAULT_WEIGHTS = {
    'strong_positive': 2,
    'weak_positive': 1,
    'neutral': 0,
    'weak_negative': -1,
    'strong_negative': -2
}
OUTPUT_DIR = 'output'

class SentimentTrendAnalyzer:
    def __init__(self, csv_path, date_col='date', label_col='sentiment_label', weights=None, time_freq='D'):
        self.csv_path = csv_path
        self.date_col = date_col
        self.label_col = label_col
        self.weights = weights if weights else DEFAULT_WEIGHTS
        self.time_freq = time_freq
        self.df = None
        self.daily_stats = None
        self.stage_info = None
        self.peaks_info = None
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

    def load_data(self):
        self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
        self.df[self.date_col] = pd.to_datetime(self.df[self.date_col])

    def compute_daily_stats(self):
        daily_counts = self.df.groupby([self.date_col, self.label_col]).size().unstack(fill_value=0)
        # 计算情绪指数
        daily_counts['sentiment_index'] = sum(
            daily_counts.get(label, 0) * weight for label, weight in self.weights.items()
        ) / daily_counts.sum(axis=1)
        # 计算情绪波动率（标准差）
        daily_counts['sentiment_std'] = self.df.groupby(self.date_col)['sentiment_score'].std()
        # 计算情绪总量
        daily_counts['total_comments'] = daily_counts[list(self.weights.keys())].sum(axis=1)
        # 计算情绪比例
        for label in self.weights.keys():
            daily_counts[f'{label}_ratio'] = daily_counts[label] / daily_counts['total_comments']
        self.daily_stats = daily_counts

    def smooth_index(self, window=3):
        self.daily_stats['sentiment_index_smooth'] = self.daily_stats['sentiment_index'].rolling(window, min_periods=1, center=True).mean()

    def detect_peaks(self, prominence=0.1):
        idx = self.daily_stats['sentiment_index_smooth'].dropna().index
        values = self.daily_stats['sentiment_index_smooth'].dropna().values
        peaks, properties = find_peaks(values, prominence=prominence)
        prominences = peak_prominences(values, peaks)[0]
        peak_dates = idx[peaks]
        # 记录每个峰值的强度、prominence、左/右基线
        peaks_info = []
        for i, d in enumerate(peak_dates):
            peaks_info.append({
                'date': str(d.date()),
                'value': float(values[peaks[i]]),
                'prominence': float(prominences[i]),
                'left_base': str(idx[properties['left_bases'][i]].date()),
                'right_base': str(idx[properties['right_bases'][i]].date())
            })
        self.peaks_info = peaks_info
        return peak_dates, peaks_info

    def segment_phases(self, threshold=0.2, min_length=2):
        # Simple phase segmentation based on sentiment index change rate: outbreak (>threshold), decline (<-threshold), stable (in between)
        idx = self.daily_stats.index
        values = self.daily_stats['sentiment_index_smooth'].values
        phases = []
        current_phase = None
        start_idx = 0
        for i in range(1, len(values)):
            diff = values[i] - values[i-1]
            if diff >= threshold:
                phase = 'outbreak'  # 爆发
            elif diff <= -threshold:
                phase = 'decline'  # 衰退
            else:
                phase = 'stable'   # 平稳
            if current_phase is None:
                current_phase = phase
                start_idx = i-1
            elif phase != current_phase:
                if i-1-start_idx+1 >= min_length:
                    phases.append({'phase': current_phase, 'start': str(idx[start_idx].date()), 'end': str(idx[i-1].date())})
                current_phase = phase
                start_idx = i-1
        # Last phase
        if start_idx < len(values)-1:
            phases.append({'phase': current_phase, 'start': str(idx[start_idx].date()), 'end': str(idx[-1].date())})
        self.stage_info = phases
        return phases

    def export_results(self):
        # 导出每日情绪统计
        daily_path = os.path.join(OUTPUT_DIR, 'daily_sentiment_stats.csv')
        self.daily_stats.to_csv(daily_path, encoding='utf-8-sig')
        # 导出爆发阶段
        stage_path = os.path.join(OUTPUT_DIR, 'sentiment_phases.json')
        with open(stage_path, 'w', encoding='utf-8') as f:
            json.dump(self.stage_info, f, ensure_ascii=False, indent=2)
        # 导出峰值信息
        peaks_path = os.path.join(OUTPUT_DIR, 'sentiment_peaks.json')
        with open(peaks_path, 'w', encoding='utf-8') as f:
            json.dump(self.peaks_info, f, ensure_ascii=False, indent=2)
        print(f"已导出分析结果到 {OUTPUT_DIR}/")

    def plot_trend(self, event_dates=None, save_path=None):
        plt.figure(figsize=(16, 8))
        # 1. Main trend line
        plt.plot(self.daily_stats.index, self.daily_stats['sentiment_index'], label='Sentiment Index', color='gray', alpha=0.5)
        plt.plot(self.daily_stats.index, self.daily_stats['sentiment_index_smooth'], label='Smoothed Sentiment Index', color='blue', linewidth=2)
        # 2. Stacked area for sentiment categories (高亮配色+透明度0.75)
        # 顺序：Strong Positive, Strong Negative, Weak Negative, Weak Positive, Neutral
        stack_labels = ['strong_positive', 'strong_negative', 'weak_negative', 'weak_positive', 'neutral']
        # Strong情绪y轴拔高
        stack_data = []
        for l in stack_labels:
            if l in self.daily_stats.columns:
                if l in ['strong_positive', 'strong_negative']:
                    stack_data.append(self.daily_stats[l] * 2.5)
                else:
                    stack_data.append(self.daily_stats[l])
        legend_color_map = {
            'strong_positive': '#ff3030',  # 高饱和红
            'weak_positive':   '#ffb347',  # 橙黄
            'neutral':         '#ffe600',  # 黄色
            'weak_negative':   '#4fc3f7',  # 浅蓝
            'strong_negative': '#3385ff'   # 高饱和蓝
        }
        pretty_labels = [l.replace('_', ' ').title() for l in stack_labels]
        stack_colors = [legend_color_map.get(l, None) for l in stack_labels]
        stack_handles = plt.stackplot(self.daily_stats.index, stack_data, labels=pretty_labels, colors=stack_colors, alpha=0.8)
        # 3. Event markers
        if event_dates:
            for ed in event_dates:
                plt.axvline(pd.to_datetime(ed), color='red', linestyle=':', alpha=0.8)
                plt.text(pd.to_datetime(ed), plt.ylim()[1], f'Event:{ed}', color='red', rotation=90, va='top', fontsize=10)
        # 4. Outbreak triangle markers and annotation
        if self.peaks_info:
            for i, peak in enumerate(self.peaks_info):
                d = pd.to_datetime(peak['date'])
                # 正三角形标记，正红色
                plt.plot(d, peak['value'], marker='^', color='#ff0000', markersize=14, zorder=10)
                # Outbreak文字竖直错开，正方向间隔更大，负方向不变
                if i % 2 == 0:
                    y_offset = 2.0 + 1.8 * (i // 2)
                    va = 'bottom'
                else:
                    y_offset = -2.2
                    va = 'top'
                plt.annotate('Outbreak', xy=(d, peak['value']), xytext=(d, peak['value']+y_offset),
                             textcoords='data', ha='center', va=va, color='#ff0000', fontsize=13, fontweight='bold', arrowprops=None)
        # 5. Phase highlight
        if self.stage_info:
            phase_label_shown = set()
            for phase in self.stage_info:
                color = {'outbreak':'#ff0000', 'stable':'#ffb6c1', 'decline':'#b39ddb'}.get(phase['phase'], '#eeeeee')
                label = phase['phase'].title() if phase['phase'] not in phase_label_shown else None
                plt.axvspan(pd.to_datetime(phase['start']), pd.to_datetime(phase['end']), color=color, alpha=0.3, label=label)
                phase_label_shown.add(phase['phase'])
        plt.xlabel('Date')
        plt.ylabel('Sentiment Index / Comment Count')
        plt.title('Sentiment Time Series Trend & Event Alignment (with Outbreak/Stable/Decline Highlight)')
        # 自定义图例配色
        handles, labels = plt.gca().get_legend_handles_labels()
        new_handles = []
        for h, l in zip(handles, labels):
            if l in pretty_labels:
                idx = pretty_labels.index(l)
                color = legend_color_map.get(stack_labels[idx], None)
                if color:
                    from matplotlib.patches import Patch
                    new_handles.append(Patch(facecolor=color, edgecolor=color, label=l, alpha=0.9))
                else:
                    new_handles.append(h)
            else:
                new_handles.append(h)
        plt.legend(new_handles, labels, loc='upper left', bbox_to_anchor=(1,1))
        plt.tight_layout()
        # 保存图片到指定output目录
        if save_path is None:
            save_path = r'D:/nus/Web_Mining/project/EmotionSense/output/sentiment_trend.png'
        plt.savefig(save_path)
        plt.show()

    def plot_ratio_bar(self, save_path=None):
        # Stacked bar chart for sentiment ratio
        plt.figure(figsize=(16, 6))
        stack_labels = list(self.weights.keys())
        def pretty_label(label):
            return label.replace('_', ' ').title()
        color_map = {
            'strong_positive': '#d73027',   # 红色
            'weak_positive':   '#fc8d9b',   # 浅粉色
            'neutral':         '#ffd700',   # 黄色
            'weak_negative':   '#91bfdb',   # 浅蓝色
            'strong_negative': '#4575b4'    # 深蓝色
        }
        bottom = np.zeros(len(self.daily_stats))
        for label in stack_labels:
            if f'{label}_ratio' in self.daily_stats.columns:
                plt.bar(self.daily_stats.index, self.daily_stats[f'{label}_ratio'], bottom=bottom, label=pretty_label(label), color=color_map.get(label, None), alpha=0.7)
                bottom += self.daily_stats[f'{label}_ratio'].values
        plt.xlabel('Date')
        plt.ylabel('Sentiment Ratio')
        plt.title('Daily Sentiment Composition')
        plt.legend()
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path)
        plt.show()

    def run(self, window=3, prominence=0.1, event_path=None, event_window=0, phase_threshold=0.2, min_phase_len=2):
        self.load_data()
        self.compute_daily_stats()
        self.smooth_index(window=window)
        peak_dates, peaks_info = self.detect_peaks(prominence=prominence)
        print(f"检测到情绪峰值日期及强度: {peaks_info}")
        self.segment_phases(threshold=phase_threshold, min_length=min_phase_len)
        print(f"自动分阶段结果: {self.stage_info}")
        self.export_results()
        # 事件对齐
        event_dates = None
        if event_path:
            if event_path.endswith('.json'):
                with open(event_path, 'r', encoding='utf-8') as f:
                    event_dates = json.load(f)
            elif event_path.endswith('.csv'):
                event_df = pd.read_csv(event_path)
                event_dates = event_df['date'].tolist()
            if event_window > 0 and event_dates:
                expanded = []
                for ed in event_dates:
                    d = pd.to_datetime(ed)
                    for offset in range(-event_window, event_window+1):
                        expanded.append((d + timedelta(days=offset)).strftime('%Y-%m-%d'))
                event_dates = expanded
        self.plot_trend(event_dates=event_dates, save_path=os.path.join(OUTPUT_DIR, 'sentiment_trend.png'))
        self.plot_ratio_bar(save_path=os.path.join(OUTPUT_DIR, 'sentiment_ratio_bar.png'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='情绪时间序列分析与可视化')
    parser.add_argument('--input', type=str, default='../data/cleaned/with_sentiment.csv', help='输入CSV路径')
    parser.add_argument('--window', type=int, default=3, help='平滑窗口大小')
    parser.add_argument('--prominence', type=float, default=0.1, help='峰值检测prominence参数')
    parser.add_argument('--event', type=str, default=None, help='事件日期文件（csv/json，需有date列或为日期列表）')
    parser.add_argument('--event_window', type=int, default=0, help='事件窗口（如±2天）')
    parser.add_argument('--phase_threshold', type=float, default=0.2, help='阶段划分阈值')
    parser.add_argument('--min_phase_len', type=int, default=2, help='阶段最小长度')
    args = parser.parse_args()

    analyzer = SentimentTrendAnalyzer(
        csv_path=args.input,
        date_col='date',
        label_col='sentiment_label',
        weights=DEFAULT_WEIGHTS,
        time_freq='D'
    )
    analyzer.run(window=args.window, prominence=args.prominence, event_path=args.event, event_window=args.event_window, phase_threshold=args.phase_threshold, min_phase_len=args.min_phase_len)
