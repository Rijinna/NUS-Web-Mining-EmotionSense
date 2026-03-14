import pandas as pd

# 1. 读取原始数据
df = pd.read_csv('D:/NUS/Web_Mining/project/EmotionSense/data/raw/posts.csv', encoding='gb18030')

# 2. 删除 source 列
if 'source' in df.columns:
    df = df.drop(columns=['source'])

# 3. 删除所有 Unnamed 列
df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

# 4. 只保留你需要的字段
keep_cols = ['user_id', 'nickname', 'text', 'forward', 'comment', 'like', 'media', 'time', 'post_url', 'mid', 'cluster_label']
df = df[[col for col in keep_cols if col in df.columns]]

print('最终保留字段:', df.columns.tolist())

# 5. 转换 time 列为日期格式
df['time'] = pd.to_datetime(df['time'], errors='coerce')

# 6. 筛选 2024年4月-10月
mask_2024 = (df['time'] >= '2024-04-01') & (df['time'] < '2024-11-01')
df_2024 = df[mask_2024].copy()

# 7. 筛选 2025年4月-7月
mask_2025 = (df['time'] >= '2025-04-01') & (df['time'] < '2025-08-01')
df_2025 = df[mask_2025].copy()

# 8. 保存为新文件
df_2024.to_csv('D:/NUS/Web_Mining/project/EmotionSense/data/cleaned/posts_2024.csv', index=False, encoding='utf-8')
df_2025.to_csv('D:/NUS/Web_Mining/project/EmotionSense/data/cleaned/posts_2025.csv', index=False, encoding='utf-8')

print(f"2024年4-10月数据量: {len(df_2024)}")
print(f"2025年4-7月数据量: {len(df_2025)}")