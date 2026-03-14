import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import argparse
import os

# 支持命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='情绪峰值检测')
    parser.add_argument('--year', type=int, default=2024, help='年份')
    parser.add_argument('--sentiment_col', type=str, default='sentiment', help='情绪列名')
    parser.add_argument('--window', type=int, default=3, help='移动平均窗口')
    parser.add_argument('--prominence', type=float, default=1, help='峰值显著性')
    parser.add_argument('--input', type=str, default=None, help='输入csv文件路径')
    parser.add_argument('--output', type=str, default=None, help='输出图片路径')
    return parser.parse_args()

def load_data(year, input_path=None):
    if input_path is not None:
        path = input_path
    else:
        path = f'../data/cleaned/with_sentiment_{year}.csv'
    df = pd.read_csv(path, encoding='utf-8')
    df['date'] = pd.to_datetime(df['timestamp'], format='%y-%m-%d %H:%M', errors='coerce').dt.floor('D')
    print('原始时间字段样例:', df['timestamp'].head() if 'timestamp' in df.columns else df['time'].head())
    print('解析后date样例:', df['date'].head())
    print('最小日期:', df['date'].min(), '最大日期:', df['date'].max())
    print('唯一年份:', pd.Series(df['date']).dt.year.unique())
    return df

def sentiment_daily_stats(df, sentiment_col='sentiment'):
    if df[sentiment_col].dtype == object:
        mapping = {'negative': -1, 'neutral': 0, 'positive': 1, 'neg': -1, 'neu': 0, 'pos': 1}
        df['sentiment_num'] = df[sentiment_col].map(mapping).fillna(0)
    else:
        df['sentiment_num'] = df[sentiment_col]
    daily = df.groupby('date')['sentiment_num'].agg(['mean', 'sum', 'count'])
    print('groupby后daily.index类型:', type(daily.index))
    print('groupby后daily.index样例:', daily.index[:10])
    print('groupby后最小日期:', daily.index.min(), '最大日期:', daily.index.max())
    return daily

def smooth_series(series, window=3):
    return series.rolling(window, center=True, min_periods=1).mean()

def detect_peaks(series, prominence=1):
    peaks, props = find_peaks(series, prominence=prominence)
    return peaks, props

def plot_trend_with_peaks(daily, peaks, col='mean', output=None):
    print('画图前daily.index类型:', type(daily.index))
    print('画图前daily.index样例:', daily.index[:10])
    plt.figure(figsize=(12,6))
    plt.plot(daily.index, daily[col], label='Sentiment Trend')
    plt.scatter(daily.index[peaks], daily[col].iloc[peaks], color='red', label='Peaks')
    plt.title('Daily Sentiment Trend with Peaks')
    plt.xlabel('Date')
    plt.ylabel('Sentiment Mean')
    plt.legend()
    plt.tight_layout()
    if output:
        plt.savefig(output)
        print(f'图已保存到 {output}')
    else:
        plt.show()

def main():
    args = parse_args()
    df = load_data(args.year, args.input)
    daily = sentiment_daily_stats(df, args.sentiment_col)
    daily['mean_smooth'] = smooth_series(daily['mean'], args.window)
    peaks, props = detect_peaks(daily['mean_smooth'], args.prominence)
    print('峰值日期:')
    for idx in peaks:
        print(daily.index[idx], '均值:', round(daily['mean_smooth'].iloc[idx], 3))
    plot_trend_with_peaks(daily, peaks, col='mean_smooth', output=args.output)

if __name__ == '__main__':
    main()
    