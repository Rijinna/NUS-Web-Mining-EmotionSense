import pandas as pd
import re
from collections import Counter
from itertools import islice

# 路径
csv_path = r'D:\nus\Web_Mining\project\EmotionSense\data\cleaned\cleaned_weibo_comments.csv'

# 停用词表（可扩展）
def load_stopwords():
    stopwords = set()
    try:
        with open('data_processing/stopwords.txt', encoding='utf-8') as f:
            for line in f:
                stopwords.add(line.strip())
    except Exception:
        # 常见停用词备选
        stopwords = set(['的', '了', '啊', '是', '我', '你', '他', '她', '它', '在', '和', '有', '也', '就', '都', '很', '还', '吗', '吧', '呢', '呀', '着', '被', '到', '说', '为', '与', '及', '或', '而', '但', '并', '其', '让', '给', '做', '去', '来', '会', '要', '能', '这', '那', '一个', '我们', '他们', '你们', '自己', '什么', '没有', '不是', '就是', '怎么', '所以', '而且', '如果', '因为', '但是', '然后', '而已', '其实', '其实', '其实', '其实'])
    return stopwords

stopwords = load_stopwords()

# 读取数据
df = pd.read_csv(csv_path, encoding='utf-8-sig')

print("===== 数据基本信息 =====")
print(f"总评论数: {len(df)}")
print(f"唯一用户数: {df['user_id'].nunique()}")
print(f"唯一帖子数: {df['post_id'].nunique()}")
print(f"时间范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"关键词数量: {df['keyword'].nunique()}")
print(f"关键词分布:\n{df['keyword'].value_counts().to_string()}")
print()

print("===== 内容长度统计 =====")
df['content_length'] = df['cleaned_content'].astype(str).str.len()
print(f"平均内容长度: {df['content_length'].mean():.2f}")
print(f"最大内容长度: {df['content_length'].max()}")
print(f"最小内容长度: {df['content_length'].min()}")
print()

print("===== 点赞/转发/评论数统计 =====")
for col in ['likes', 'forwards', 'comments']:
    if col in df.columns:
        print(f"{col} 平均: {df[col].mean():.2f}，最大: {df[col].max()}，最小: {df[col].min()}")
print()

print("===== 日期分布（前10天） =====")
print(df['date'].value_counts().sort_index().head(10).to_string())
print()

print("===== 用户活跃度Top10 =====")
print(df['user_name'].value_counts().head(10).to_string())
print()

# ================== 文本特征统计 ==================
print("===== 评论文本特征统计 =====")

all_text = ' '.join(df['cleaned_content'].astype(str).tolist())

# 分词（优先jieba，否则正则）
try:
    import jieba
    words = jieba.lcut(all_text)
    words = [w.strip() for w in words if w.strip() and len(w.strip()) > 1 and w not in stopwords]
except ImportError:
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', all_text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]

# 高频词统计（去除停用词）
word_counter = Counter(words)
print("高频词Top20（去除停用词）:")
for w, c in word_counter.most_common(20):
    print(f"{w}: {c}")
print()

# 高频短语（n-gram）统计

def ngrams(lst, n):
    return zip(*(islice(lst, i, None) for i in range(n)))

def filter_ngram(ng):
    # 只保留不含停用词的短语
    return all(w not in stopwords for w in ng)

for n in [2, 3]:
    ngram_counter = Counter([''.join(ng) for ng in ngrams(words, n) if filter_ngram(ng)])
    print(f"高频{n}-gram短语Top20（去除停用词）:")
    for ng, c in ngram_counter.most_common(20):
        print(f"{ng}: {c}")
    print()

# 常见表情符号（匹配微博/微信表情、颜文字、emoji等）
emoji_pattern = re.compile(
    "["
    u"\U0001F600-\U0001F64F"  # Emoticons
    u"\U0001F300-\U0001F5FF"  # Symbols & Pictographs
    u"\U0001F680-\U0001F6FF"  # Transport & Map
    u"\U0001F1E0-\U0001F1FF"  # Flags
    u"\U00002700-\U000027BF"  # Dingbats
    u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    u"\U00002600-\U000026FF"  # Misc symbols
    u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "]+", flags=re.UNICODE
)
all_emojis = emoji_pattern.findall(all_text)
emoji_counter = Counter(all_emojis)
print("常见emoji/表情符号Top20:")
for e, c in emoji_counter.most_common(20):
    print(f"{e}: {c}")
print()

# 常见网络流行语（建议从高频短语中人工挑选，补充到情感词典）
print("（建议从高频短语中人工挑选网络流行语，补充到情感词典）")
print()

# 常见标点符号统计
punct_counter = Counter(re.findall(r'[，。！？!?.、~…（）()“”"\'\-——：:；;·@#￥%&*+=<>【】\[\]]', all_text))
print("常见标点符号Top20:")
for p, c in punct_counter.most_common(20):
    print(f"{p}: {c}")
print()

# 内容长度分布
print("内容长度分布（每10字一个区间，前10区间）:")
length_bins = pd.cut(df['content_length'], bins=range(0, 101, 10), right=False)
print(df.groupby(length_bins).size().head(10))