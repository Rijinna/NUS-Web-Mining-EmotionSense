import pickle
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
import sys
from collections import Counter

# 1. 加载图
def load_graph(year=2024):
    path = f'../data/cleaned/hetero_weibo_graph_{year}.gpickle'
    with open(path, 'rb') as f:
        G = pickle.load(f)
    print(f"图加载完成: {G.number_of_nodes()} 个节点, {G.number_of_edges()} 条边")
    return G

# 2. 节点类型分布统计
def node_type_stats(G):
    node_types = pd.Series(nx.get_node_attributes(G, 'type')).value_counts()
    print("节点类型分布：\n", node_types)
    node_types.plot(kind='bar', title='Node Type Distribution', color='lightblue')
    plt.show()

# 3. 活跃度与情绪分布统计
def activity_and_sentiment_stats(G, date=None):
    # 用户活跃度统计
    user_nodes = [n for n, d in G.nodes(data=True) if d['type'] == 'user']
    user_comment_count, user_post_count = Counter(), Counter()
    for u in user_nodes:
        for _, v, d in G.out_edges(u, data=True):
            if d['type'] == 'comment':
                user_comment_count[u] += 1
            if d['type'] == 'post':
                user_post_count[u] += 1
    top_comment_users = user_comment_count.most_common(10)
    top_post_users = user_post_count.most_common(10)

    # Top 评论用户柱状图
    plt.figure(figsize=(8,4))
    users = [uid[-6:] for uid, _ in top_comment_users]
    counts = [c for _, c in top_comment_users]
    plt.bar(users, counts, color='skyblue')
    plt.title("Top 10 Users by Comments")
    plt.xlabel("User ID (suffix)")
    plt.ylabel("Comments")
    plt.show()

    # Top 发帖用户柱状图
    plt.figure(figsize=(8,4))
    users = [uid[-6:] for uid, _ in top_post_users]
    counts = [c for _, c in top_post_users]
    plt.bar(users, counts, color='orange')
    plt.title("Top 10 Users by Posts")
    plt.xlabel("User ID (suffix)")
    plt.ylabel("Posts")
    plt.show()

    # 情绪分布分析
    if date:
        comment_nodes = [n for n, d in G.nodes(data=True) if d['type'] == 'comment' and d['date'] == date]
    else:
        comment_nodes = [n for n, d in G.nodes(data=True) if d['type'] == 'comment']
    sentiments = [G.nodes[n].get('sentiment') for n in comment_nodes]
    sentiment_map = {0: 'Negative', 1: 'Neutral', 2: 'Positive'}
    sentiments = [sentiment_map.get(s, 'Unknown') for s in sentiments]

    sentiment_counts = pd.Series(sentiments).value_counts()
    # 柱状图
    sentiment_counts.plot(kind='bar', color=['red', 'gray', 'green'], title=f"Sentiment Distribution ({'All' if not date else date})")
    plt.xlabel("Sentiment")
    plt.ylabel("Number of Comments")
    plt.show()
    # 饼图
    sentiment_counts.plot(kind='pie', autopct='%1.1f%%', startangle=90, colors=['red', 'gray', 'green'])
    plt.title(f"Sentiment Proportion ({'All' if not date else date})")
    plt.ylabel("")
    plt.show()


# 4. 传播链路可视化（某天/某用户/某微博的子图）
def visualize_subgraph(G, date=None, user_id=None, post_id=None):
    if date:
        sub_nodes = [n for n, d in G.nodes(data=True) if d.get('date') == date]
        title = f"Subgraph on {date}"
    elif user_id:
        sub_nodes = [user_id] + [v for _, v in G.out_edges(user_id)]
        title = f"Subgraph of User {user_id[-6:]}"
    elif post_id:
        sub_nodes = [post_id] + [u for u, _ in G.in_edges(post_id)] + [v for _, v in G.out_edges(post_id)]
        title = f"Subgraph of Post {post_id}"
    else:
        print("Please specify date, user_id, or post_id.")
        return
    H = G.subgraph(sub_nodes)
    pos = nx.spring_layout(H, seed=42)

    # 节点颜色映射
    color_map = {'user': 'skyblue', 'post': 'orange', 'comment': 'lightgreen', 'date': 'gray'}
    node_colors = [color_map.get(H.nodes[n].get('type'), 'pink') for n in H.nodes]
    node_sizes = [100 if H.nodes[n]['type'] == 'user' else 50 for n in H.nodes]

    plt.figure(figsize=(10, 8))
    nx.draw_networkx_nodes(H, pos, node_size=node_sizes, node_color=node_colors, alpha=0.8)
    nx.draw_networkx_edges(H, pos, alpha=0.4)
    plt.title(title)
    
    # 图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='skyblue', label='User'),
        Patch(facecolor='orange', label='Post'),
        Patch(facecolor='lightgreen', label='Comment'),
        Patch(facecolor='gray', label='Date'),
    ]
    plt.legend(handles=legend_elements, loc='best')
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    # 支持命令行参数选择年份和日期
    year = 2024
    date = None
    user_id = None
    post_id = None
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.isdigit() and len(arg) == 4:
                year = int(arg)
            elif arg.startswith('date='):
                date = arg.split('=')[1]
            elif arg.startswith('user='):
                user_id = arg.split('=')[1]
            elif arg.startswith('post='):
                post_id = arg.split('=')[1]
    G = load_graph(year)
    node_type_stats(G)
    activity_and_sentiment_stats(G, date)
    visualize_subgraph(G, date=date, user_id=user_id, post_id=post_id)
