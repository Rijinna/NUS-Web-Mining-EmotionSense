import pandas as pd 
import re
from glob import glob
import os
from pathlib import Path

def clean_content(text):
    if pd.isna(text) or text == "":
        return ""
    text = re.sub(r'http[s]?://\S+', '', text)
    # text = re.sub(r'\[[^\]]+\]', '', text)  # 不再去除微博表情
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_weibo_timestamp(ts):
    # 只处理类似 25-1-30 22:48 这种格式
    try:
        dt = pd.to_datetime(ts, format='%y-%m-%d %H:%M', errors='coerce')
        # 如果年份小于当前年份（如25），自动补全为2025年
        if pd.notnull(dt) and dt.year < 100:
            dt = dt.replace(year=2000 + dt.year)
        return dt.date() if pd.notnull(dt) else pd.NaT
    except:
        return pd.NaT

def main():
    # 🔧 确定输入文件路径（原始数据）
    raw_folder = r'D:\nus\Web_Mining\project\EmotionSense\data\raw'
    cleaned_folder = r'D:\nus\Web_Mining\project\EmotionSense\data\cleaned'
    
    # 🔧 获取所有 raw 数据文件
    files = sorted(glob(os.path.join(raw_folder, 'period_*.csv')))
    if not files:
        print("❌ 未找到原始 period_*.csv 文件，请检查路径")
        return

    # 📖 合并数据
    df = pd.concat([pd.read_csv(f, encoding='utf-8-sig') for f in files], ignore_index=True)

    # 🧹 清洗内容
    df['cleaned_content'] = df['content'].apply(clean_content)
    
    # 过滤掉包含特定广告语的评论
    df = df[~df['cleaned_content'].str.contains('快来与志同道合的小伙伴', na=False)]
    df = df[~df['cleaned_content'].str.contains('同城小伙伴', na=False)]
    
    # 🕓 解析时间
    df['date'] = df['timestamp'].apply(parse_weibo_timestamp)

    # ✅ ✅ ✅ 加入过滤：去除 2025-07-01 之后的评论
    #df = df[df['date'] <= pd.to_datetime('2024-10-05').date()]

    # 🧼 移除空评论
    df = df[df['cleaned_content'].str.len() > 0]

    # 🚩 去重：基于 content、user_id、post_id 三列
    before = len(df)
    df = df.drop_duplicates(subset=['content', 'user_id', 'post_id'], keep='first')
    after = len(df)
    print(f"去重前: {before} 条，去重后: {after} 条")

    # 💾 保存清洗后的数据
    Path(cleaned_folder).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(cleaned_folder, 'cleaned_weibo_comments.csv')
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"✅ 数据清洗完成，已保存到：{output_path}")

if __name__ == "__main__":
    main()
