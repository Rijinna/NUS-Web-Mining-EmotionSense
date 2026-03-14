import argparse
import os
import networkx as nx
import dgl
import torch
import numpy as np
from collections import defaultdict
import pandas

# 1. 读取NetworkX图
def load_graph(year):
    path = f'../data/cleaned/hetero_weibo_graph_{year}.gpickle'
    G_nx = nx.read_gpickle(path)
    print(f'Loaded graph: {G_nx.number_of_nodes()} nodes, {G_nx.number_of_edges()} edges')
    return G_nx

# 2. 自动推断节点/边类型，构建异构图
def nx_to_dgl_hetero(G_nx):
    # 节点类型推断
    node_type_dict = {}
    for n, attr in G_nx.nodes(data=True):
        t = attr.get('type', None)
        if t is None or t == 'unk':
            # 用前缀推断
            prefix = n.split('_')[0] if '_' in n else n[:4]
            t = prefix
        node_type_dict[n] = t
    node_types = set(node_type_dict.values())
    # 为每种类型分配连续id
    node_id_map = {ntype: {} for ntype in node_types}
    node_type_count = {ntype: 0 for ntype in node_types}
    for n, ntype in node_type_dict.items():
        node_id_map[ntype][n] = node_type_count[ntype]
        node_type_count[ntype] += 1
    # 边类型推断
    edge_type_dict = {}
    edge_types = set()
    edge_tuples = defaultdict(lambda: ([], []))
    for u, v, attr in G_nx.edges(data=True):
        etype = attr.get('type', 'unk')
        edge_type_dict[(u, v)] = etype
        edge_types.add(etype)
        utype = node_type_dict[u]
        vtype = node_type_dict[v]
        edge_tuples[(utype, etype, vtype)][0].append(node_id_map[utype][u])
        edge_tuples[(utype, etype, vtype)][1].append(node_id_map[vtype][v])
    # 构造异构图
    data_dict = {k: (torch.tensor(v[0]), torch.tensor(v[1])) for k, v in edge_tuples.items()}
    num_nodes_dict = {ntype: node_type_count[ntype] for ntype in node_types}
    G_hetero = dgl.heterograph(data_dict, num_nodes_dict)
    print('异构图结构:', G_hetero)
    print('节点类型:', node_types)
    print('边类型:', list(edge_tuples.keys()))
    return G_hetero, node_id_map, node_type_dict

# 3. 为每种节点类型分配特征
def build_hetero_features(G_nx, node_id_map):
    node_feats = {}
    for ntype, id_map in node_id_map.items():
        feats = []
        for n in sorted(id_map, key=lambda x: id_map[x]):
            attr = G_nx.nodes[n]
            s = attr.get('sentiment', 0)
            if s is None or (isinstance(s, float) and np.isnan(s)):
                s = 0.0
            sentiment = float(s)
            degree = G_nx.degree[n]
            feats.append([sentiment, degree])
        node_feats[ntype] = torch.tensor(feats, dtype=torch.float32)
    return node_feats

# 4. HeteroGNN模型
import torch.nn as nn
import dgl.nn as dglnn
class SimpleHeteroGNN(nn.Module):
    def __init__(self, in_feats, h_feats, out_feats, rel_names, ntypes):
        super().__init__()
        self.conv1 = dglnn.HeteroGraphConv({rel: dglnn.GraphConv(in_feats, h_feats) for rel in rel_names}, aggregate='sum')
        self.conv2 = dglnn.HeteroGraphConv({rel: dglnn.GraphConv(h_feats, out_feats) for rel in rel_names}, aggregate='sum')
        self.ntypes = ntypes
    def forward(self, g, inputs):
        h = self.conv1(g, inputs)
        h = {k: torch.relu(v) for k, v in h.items()}
        h = self.conv2(g, h)
        return h

def get_post_labels(year, node_id_map):
    import pandas as pd
    # 读取评论数据
    comments = pd.read_csv(f'../data/cleaned/with_sentiment_{year}.csv')
    # 统计每个post的评论情绪均值
    post_sentiment = comments.groupby('post_id')['sentiment_score'].mean()
    # post节点顺序
    post_nodes = sorted(node_id_map['post'], key=lambda x: node_id_map['post'][x])
    # 生成标签张量，顺序与post节点顺序一致
    post_labels = []
    for n in post_nodes:
        # n形如'post_xxx'，取xxx
        post_id = n.replace('post_', '')
        label = post_sentiment.get(post_id, 0.0)
        post_labels.append(label)
    post_labels = torch.tensor(post_labels, dtype=torch.float32)
    return post_labels

# 5. 主流程
def main():
    parser = argparse.ArgumentParser(description='异构GNN情绪/热度传播建模')
    parser.add_argument('--year', type=int, default=2024)
    parser.add_argument('--task', type=str, default='node_classification', choices=['node_classification', 'link_prediction'])
    parser.add_argument('--dynamic', action='store_true', help='是否按天分片动态图')
    args = parser.parse_args()

    G_nx = load_graph(args.year)
    G_hetero, node_id_map, node_type_dict = nx_to_dgl_hetero(G_nx)
    node_feats = build_hetero_features(G_nx, node_id_map)

    # === 标签统计与mask划分 ===
    post_labels = get_post_labels(args.year, node_id_map)  # [num_post]
    num_post = post_labels.shape[0]
    idx = np.arange(num_post)
    np.random.shuffle(idx)
    train_idx = idx[:int(0.8*num_post)]
    val_idx = idx[int(0.8*num_post):int(0.9*num_post)]
    test_idx = idx[int(0.9*num_post):]
    train_mask = torch.zeros(num_post, dtype=torch.bool)
    val_mask = torch.zeros(num_post, dtype=torch.bool)
    test_mask = torch.zeros(num_post, dtype=torch.bool)
    train_mask[train_idx] = True
    val_mask[val_idx] = True
    test_mask[test_idx] = True

    # === GNN训练/评估主流程（回归任务示例） ===
    if args.task == 'node_classification':
        rel_names = list(G_hetero.etypes)
        ntypes = list(G_hetero.ntypes)
        in_feats = next(iter(node_feats.values())).shape[1]
        model = SimpleHeteroGNN(in_feats, 32, 1, rel_names, ntypes)  # 输出1维，回归
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        loss_fn = torch.nn.MSELoss()
        for epoch in range(1, 21):
            model.train()
            logits = model(G_hetero, node_feats)['post'].squeeze()  # [num_post]
            loss = loss_fn(logits[train_mask], post_labels[train_mask])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            # 验证
            model.eval()
            with torch.no_grad():
                val_loss = loss_fn(logits[val_mask], post_labels[val_mask])
                test_loss = loss_fn(logits[test_mask], post_labels[test_mask])
            print(f'Epoch {epoch}: train_loss={loss.item():.4f} val_loss={val_loss.item():.4f} test_loss={test_loss.item():.4f}')
        print('异构节点回归任务完成（示例）')
    else:
        print('暂未实现其他任务')

if __name__ == '__main__':
    main()
