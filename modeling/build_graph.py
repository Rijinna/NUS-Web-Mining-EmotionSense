 # 构建用户交互图（评论-用户-转发边）
import pandas as pd
import networkx as nx
from tqdm import tqdm
import os
import sys

def get_unique_comment_id(row):
    return f"comment_{row.get('user_id', 'u')}_{row.get('post_id', 'p')}_{str(row.get('timestamp', row.get('date', 'd')))}_{row.name}"

def add_user_nodes(G, user_ids, nicknames=None):
    for i, uid in enumerate(user_ids):
        if not G.has_node(f"user_{uid}"):
            G.add_node(f"user_{uid}", type='user', nickname=nicknames[i] if nicknames is not None else "")

def add_date_nodes(G, dates):
    for d in set(dates):
        if not G.has_node(f"date_{d}"):
            G.add_node(f"date_{d}", type='date')

def main(year=2024):
    try:
        posts = pd.read_csv(f'../data/cleaned/posts_{year}.csv', encoding='utf-8')
        comments = pd.read_csv(f'../data/cleaned/with_sentiment_{year}.csv', encoding='utf-8')
    except Exception as e:
        print(f"读取{year}年数据失败:", e)
        return

    posts['date'] = pd.to_datetime(posts['time']).dt.date
    comments['date'] = pd.to_datetime(comments['timestamp']).dt.date

    G = nx.MultiDiGraph()

    # 4. 添加微博节点、用户节点、微博-用户边、微博-日期边
    for _, row in tqdm(posts.iterrows(), total=len(posts), desc='微博节点'):
        post_id = f"post_{row['mid']}"
        user_id = f"user_{row['user_id']}"
        date_id = f"date_{row['date']}"
        # 微博节点
        G.add_node(post_id, type='post', text=row['text'], forward=row['forward'], comment=row['comment'],
                   like=row['like'], media=row['media'], cluster_label=row['cluster_label'], date=str(row['date']))
        # 用户节点
        G.add_node(user_id, type='user', nickname=row['nickname'])
        # 用户-微博 发帖边
        G.add_edge(user_id, post_id, type='post', time=str(row['date']))
        # 微博-日期边
        G.add_node(date_id, type='date')
        G.add_edge(post_id, date_id, type='on_date')

    for _, row in tqdm(comments.iterrows(), total=len(comments), desc='评论节点'):
        comment_id = get_unique_comment_id(row)
        user_id = f"user_{row['user_id']}"
        date_id = f"date_{row['date']}"
        G.add_node(comment_id, type='comment', content=row['content'], sentiment=row.get('sentiment', None), date=str(row['date']))
        G.add_edge(user_id, comment_id, type='comment', time=str(row['date']), sentiment=row.get('sentiment', None))
        G.add_edge(comment_id, date_id, type='on_date')
        if pd.notna(row.get('post_id', None)):
            post_id = f"post_{row['post_id']}"
            if post_id in G.nodes:
                G.add_edge(comment_id, post_id, type='comment_to_post')

    for _, row in tqdm(comments.iterrows(), total=len(comments), desc='用户-日期活跃'):
        user_id = f"user_{row['user_id']}"
        date_id = f"date_{row['date']}"
        G.add_edge(user_id, date_id, type='active_on')

    out_path = f'../data/cleaned/hetero_weibo_graph_{year}.gpickle'
    import pickle
    with open(out_path, 'wb') as f:
        pickle.dump(G, f)
    print(f"图构建完成: {G.number_of_nodes()} 个节点, {G.number_of_edges()} 条边")
    print("图文件大小:", round(os.path.getsize(out_path) / 1024, 2), "KB")

if __name__ == "__main__":
    # 支持命令行参数选择年份
    year = 2024
    if len(sys.argv) > 1:
        try:
            year = int(sys.argv[1])
        except Exception:
            print("年份参数无效，默认使用2024年")
    main(year)