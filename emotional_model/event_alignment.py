import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import json
import os
from scipy.stats import ttest_ind, mannwhitneyu
from datetime import timedelta

# ========== 工具函数 ==========
def load_events(event_path):
    if event_path.endswith('.json'):
        with open(event_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
        return pd.DataFrame(events)
    elif event_path.endswith('.csv'):
        return pd.read_csv(event_path)
    else:
        raise ValueError('Unsupported event file format')

def extract_event_windows(daily_df, event_df, window=3):
    """
    提取每个事件窗口内的情绪数据，返回列表，每个元素为dict：
    {event_name, event_type, event_date, window_df, before_df, after_df}
    """
    results = []
    daily_df['date'] = pd.to_datetime(daily_df['date'])
    for _, row in event_df.iterrows():
        event_name = row.get('event', row.get('name', ''))
        event_type = row.get('type', '')
        event_date = pd.to_datetime(row['date'])
        mask = (daily_df['date'] >= event_date - timedelta(days=window)) & (daily_df['date'] <= event_date + timedelta(days=window))
        window_df = daily_df[mask].copy()
        before_df = daily_df[(daily_df['date'] < event_date - timedelta(days=window)) & (daily_df['date'] >= event_date - timedelta(days=window*2))].copy()
        after_df = daily_df[(daily_df['date'] > event_date + timedelta(days=window)) & (daily_df['date'] <= event_date + timedelta(days=window*2))].copy()
        results.append({
            'event_name': event_name,
            'event_type': event_type,
            'event_date': event_date,
            'window_df': window_df,
            'before_df': before_df,
            'after_df': after_df
        })
    return results

# ========== 统计与可视化 ==========
def plot_event_window(window_df, event_name, event_date, save_dir):
    plt.figure(figsize=(10,5))
    plt.plot(window_df['date'], window_df['sentiment_index'], marker='o', label='Sentiment Index')
    plt.axvline(event_date, color='red', linestyle='--', label='Event')
    plt.title(f'Sentiment Trend Around Event: {event_name}')
    plt.xlabel('Date')
    plt.ylabel('Sentiment Index')
    plt.legend()
    plt.tight_layout()
    save_path = os.path.join(save_dir, f'{event_name}_trend.png')
    plt.savefig(save_path)
    plt.close()
    return save_path

def event_stats(window_df, before_df, after_df):
    # 统计窗口内均值、极值、变化幅度
    stats = {}
    stats['window_mean'] = window_df['sentiment_index'].mean()
    stats['window_max'] = window_df['sentiment_index'].max()
    stats['window_min'] = window_df['sentiment_index'].min()
    stats['window_std'] = window_df['sentiment_index'].std()
    stats['before_mean'] = before_df['sentiment_index'].mean() if not before_df.empty else np.nan
    stats['after_mean'] = after_df['sentiment_index'].mean() if not after_df.empty else np.nan
    stats['delta_before'] = stats['window_mean'] - stats['before_mean'] if not np.isnan(stats['before_mean']) else np.nan
    stats['delta_after'] = stats['after_mean'] - stats['window_mean'] if not np.isnan(stats['after_mean']) else np.nan
    # 滞后/回弹天数（简单：窗口内最大/最小点与事件日的距离）
    if not window_df.empty:
        max_idx = window_df['sentiment_index'].idxmax()
        min_idx = window_df['sentiment_index'].idxmin()
        stats['lag_days'] = (window_df.loc[max_idx, 'date'] - window_df['date'].min()).days
        stats['rebound_days'] = (window_df['date'].max() - window_df.loc[min_idx, 'date']).days
    else:
        stats['lag_days'] = np.nan
        stats['rebound_days'] = np.nan
    # 显著性检验
    if not before_df.empty and not window_df.empty:
        try:
            t_stat, t_p = ttest_ind(before_df['sentiment_index'], window_df['sentiment_index'], nan_policy='omit')
            u_stat, u_p = mannwhitneyu(before_df['sentiment_index'], window_df['sentiment_index'], alternative='two-sided')
        except Exception:
            t_stat, t_p, u_stat, u_p = np.nan, np.nan, np.nan, np.nan
        stats['t_p'] = t_p
        stats['u_p'] = u_p
    else:
        stats['t_p'] = np.nan
        stats['u_p'] = np.nan
    return stats

# ========== Markdown报告生成 ==========
def generate_markdown_report(event_results, save_dir):
    md_lines = ['# Event Alignment Sentiment Report\n']
    for res in event_results:
        md_lines.append(f"## Event: {res['event_name']} ({res['event_date'].date()})")
        md_lines.append(f"- Type: {res['event_type']}")
        md_lines.append(f"- Window Mean: {res['stats']['window_mean']:.3f}")
        md_lines.append(f"- Before Mean: {res['stats']['before_mean']:.3f}")
        md_lines.append(f"- After Mean: {res['stats']['after_mean']:.3f}")
        md_lines.append(f"- Max: {res['stats']['window_max']:.3f}, Min: {res['stats']['window_min']:.3f}")
        md_lines.append(f"- Delta Before: {res['stats']['delta_before']:.3f}, Delta After: {res['stats']['delta_after']:.3f}")
        md_lines.append(f"- Lag Days: {res['stats']['lag_days']}, Rebound Days: {res['stats']['rebound_days']}")
        md_lines.append(f"- t-test p: {res['stats']['t_p']:.3g}, Mann-Whitney U p: {res['stats']['u_p']:.3g}")
        md_lines.append(f"![]({os.path.basename(res['trend_img'])})\n")
    report_path = os.path.join(save_dir, 'event_alignment_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"Markdown报告已保存到: {report_path}")

# ========== 主函数 ==========
def main():
    parser = argparse.ArgumentParser(description='Event Alignment Sentiment Analysis')
    parser.add_argument('--event', type=str, required=True, help='事件文件（CSV/JSON，需含date列）')
    parser.add_argument('--daily', type=str, required=True, help='每日情绪统计CSV')
    parser.add_argument('--window', type=int, default=3, help='事件窗口（±N天）')
    parser.add_argument('--out', type=str, default='output/event_alignment', help='输出目录')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    event_df = load_events(args.event)
    daily_df = pd.read_csv(args.daily, encoding='utf-8-sig')
    daily_df['date'] = pd.to_datetime(daily_df['date'])
    event_results = []
    for res in extract_event_windows(daily_df, event_df, window=args.window):
        trend_img = plot_event_window(res['window_df'], res['event_name'], res['event_date'], args.out)
        stats = event_stats(res['window_df'], res['before_df'], res['after_df'])
        event_results.append({**res, 'trend_img': trend_img, 'stats': stats})
    generate_markdown_report(event_results, args.out)

if __name__ == '__main__':
    main()
