import pandas as pd
import numpy as np
import logging
from pathlib import Path
import json
from typing import List, Dict, Tuple
import re

# 尝试导入不同的情感分析库
try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    print("SnowNLP 未安装，将跳过 SnowNLP 分析")

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("jieba 未安装，将跳过 jieba 分词")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def count_non_overlapping_patterns_global(text, patterns):
    # 按pattern长度降序，优先长表达
    patterns = sorted(patterns, key=lambda p: -len(p))
    matched_spans = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            span = m.span()
            # 检查是否与已命中span重叠
            if not any(max(span[0], s[0]) < min(span[1], s[1]) for s in matched_spans):
                matched_spans.append(span)
    return len(matched_spans), matched_spans

class SentimentAnalyzer:
    def __init__(self):
        # 正面情感关键词（常用形容词/情绪词）
        self.positive_words = set([
            '好', '棒', '赞', '喜欢', '爱', '萌', '甜', '帅', '酷', '美', '满意', '开心','耶','漂亮','真好',
            '靓','乖','可爱','哇','潮','亲亲','羡慕','幸运','心动','丑萌','好评','期待','支持','宝宝','想要',
            '快乐', '优秀', '完美', '精彩', '绝', '牛', '太强', '香', '上头', '冲','出吗', '问价','想买',
            '欧皇', '欧气', '隐藏', '热款', '神', '天选', '一发', '神颜','可愛','嘻嘻','激动','颜值',
            '亲签', '摆柜', '限定', '限量', '绝版','拉布布','打call','厲害','鼓掌','锦鲤','有趣','精致'
        ])

        self.negative_words_strong = set([
            '垃圾', '讨厌', '烂', '糟', '恨', '崩溃', '恶心', '烦死', '裂开', '死', '烂透', '诈骗','吓',
            '难看', '丑', '吐', '崩', '有病', '滚', '傻', '神经病', '狗都不买','抢钱','坑钱','坑人',
            '雷', '翻车', '诈骗',  '弃坑', '骗', '隐瞒','退坑','sb','蠢','后悔','土','智商税','奇葩',
            '圈钱', '脱粉','凭什么', '差', '下头','假', '黑', '不配', '血亏','不值','避雷','韭菜','冲动'
        ])
        
        self.negative_words_weak = set([
            '无语','贵', '晕', '气死', '剁手', '烦', '失望', '难过', '伤心', '痛苦', '绝望','没钱',
            '有点丑', '没意思', '不喜欢', '抢不到', '不懂','不理解','悲伤','疯了','服了','呃','穷','醉了',
            '非酋', '重复', '撞款', '瑕', '背刺', '缺货', '溢价', '离谱','害怕','霉', '冲动消费',
            '生气', '愤怒','不理智','冤种','踩雷','壁垒','炒', '买不起', '吃土', '没钱', '不买','理解不了',
            '跟风','审美不行','资本','严重','割','黑线'
        ])

        # 表情符号增强
        self.positive_emojis = ['哈哈', '😂', '🥰', '😍', '❤️', '👍', '✨', '🥹', '冲鸭', '💖','送花花','心',
                                '🤩', '🎉', '💯', '🔥', '🌟', '💕', '😘', '🦄', '🌈', '👑', '🎊']
        self.negative_emojis = ['🤮', '😡', '💀', '🤡', '🙄', '😢', '😭', '无语', '裂开',
                                '👎', '💔', '😤', '😨', '😰', '😱', '💣', '☠️', '🚮', '❌']

        # 正面表达模式增强
        self.positive_patterns = [
            r'好看', r'买爆', r'爱了爱了', r'太可爱', r'无敌', r'牛逼', r'666+', r'绝绝子', r'顶流',
            r'炸裂', r'买买买', r'冲冲冲', r'抢到了', r'下单了', r'太棒了', r'我哭死', r'可爱爆', 
            r'宠粉', r'上头了', r'爱死了', r'狠狠', r'太可爱', r'call{2,}', 
            r'绝了', r'买疯了', r'好萌', r'被种草了', r'我好爱',r'啊啊',r'不愧是',
            r'一发入魂', r'欧皇附体',r'神仙颜值', r'梦中情娃', 
            r'C位', r'完美品相', r'必冲', r'亲妈', 
            r'拆出隐藏',  r'欧气爆棚', r'锦鲤体质',
            r'好价', r'拆袋快乐', r'毕业款', r'必入款', r'美神降临', r'yyds'
        ]

        # 负面表达模式分层增强
        self.negative_patterns_strong = [
            r'烂透了', r'垃圾玩意', r'气死我了', r'恶心死了', r'烂到家了', r'丑死了', r'不买',
            r'真的服了', r'一言难尽', r'丑爆了', r'丑哭了', r'被雷到了', r'这谁要啊',
            r'大翻车', r'地狱', r'雷中雷', r'盗版', r'诈骗盲盒', r'瑕疵',  r'骗子死全家', r'货不对板',
            r'必死', r'倒闭', r'吐了', r'品控'
        ]

        self.negative_patterns_weak = [
            r'无语了', r'我晕', r'剁手', r'再买就剁手', r'饥饿营销', r'抢不到', r'丑拒', r'浪费钱', 
            r'抢破头', r'太难抢', r'不感兴趣', r'踩雷了', r'审美疲劳', r'不如以前', r'审美降级',
        ]


    def analyze_with_snownlp(self, text: str) -> Dict[str, float]:
        """使用 SnowNLP 进行情感分析"""
        if not SNOWNLP_AVAILABLE:
            return {"sentiment_score": 0.0, "method": "snownlp_unavailable"}
        
        try:
            s = SnowNLP(text)
            sentiment_score = s.sentiments  # 0-1之间，越接近1越正面
            
            # 转换为 -1 到 1 的范围
            normalized_score = (sentiment_score - 0.5) * 2
            
            return {
                "sentiment_score": normalized_score,
                "confidence": abs(normalized_score),
                "method": "snownlp"
            }
        except Exception as e:
            logger.warning(f"SnowNLP 分析失败: {e}")
            return {"sentiment_score": 0.0, "method": "snownlp_error"}
    
    def analyze_with_dict(self, text: str) -> Dict[str, float]:
        """使用词典方法进行情感分析"""
        if not JIEBA_AVAILABLE:
            return {"sentiment_score": 0.0, "method": "dict_unavailable"}
        
        try:
            words = jieba.lcut(text)
            total_score = 0
            word_count = 0
            
            for word in words:
                if word in self.positive_words:
                    total_score += 1.0
                    word_count += 1
                elif word in self.negative_words_strong:
                    total_score -= 1.0
                    word_count += 1
                elif word in self.negative_words_weak:
                    total_score -= 0.5
                    word_count += 1
            
            if word_count == 0:
                return {"sentiment_score": 0.0, "method": "dict_no_words"}
            
            avg_score = total_score / word_count
            # 限制在 -1 到 1 之间
            normalized_score = max(-1.0, min(1.0, avg_score))
            
            # 置信度自适应：词数越多置信度越高，最多1.0
            confidence = min(1.0, word_count / 5)
            
            return {
                "sentiment_score": normalized_score,
                "confidence": confidence,
                "method": "dict",
                "word_count": word_count
            }
        except Exception as e:
            logger.warning(f"词典分析失败: {e}")
            return {"sentiment_score": 0.0, "method": "dict_error"}
    
    def analyze_with_keywords(self, text: str) -> Dict[str, float]:
        """基于关键词的情感分析"""
        # 全局唯一span集合，统计正面、强负面、弱负面pattern命中数
        all_spans = []
        pos_count, pos_spans = count_non_overlapping_patterns_global(text, self.positive_patterns)
        all_spans.extend(pos_spans)
        # 负面pattern计数时排除已被正面pattern覆盖的span
        def count_patterns_exclude_spans(patterns, exclude_spans):
            patterns = sorted(patterns, key=lambda p: -len(p))
            matched_spans = []
            for pat in patterns:
                for m in re.finditer(pat, text):
                    span = m.span()
                    if not any(max(span[0], s[0]) < min(span[1], s[1]) for s in matched_spans+exclude_spans):
                        matched_spans.append(span)
            return len(matched_spans), matched_spans
        neg_count_strong, neg_spans_strong = count_patterns_exclude_spans(self.negative_patterns_strong, all_spans)
        all_spans.extend(neg_spans_strong)
        neg_count_weak, neg_spans_weak = count_patterns_exclude_spans(self.negative_patterns_weak, all_spans)
        # 统计总命中数
        total_count = pos_count + neg_count_strong + neg_count_weak
        if total_count == 0:
            return {"sentiment_score": 0.0, "method": "keywords_no_match"}
        sentiment_score = (pos_count - neg_count_strong - 0.5 * neg_count_weak) / total_count
        confidence = min(1.0, total_count / 5)
        return {
            "sentiment_score": sentiment_score,
            "confidence": confidence,
            "method": "keywords",
            "positive_count": pos_count,
            "negative_count_strong": neg_count_strong,
            "negative_count_weak": neg_count_weak
        }
    
    def analyze_with_fine_grained_dict(self, text: str) -> Dict[str, float]:
        score = 0
        strong_pos, weak_pos, strong_neg, weak_neg = 0, 0, 0, 0

        # 1. pattern/词典分级
        for w in self.positive_words:
            if w in text:
                weak_pos += 1
        for w in self.negative_words_strong:
            if w in text:
                strong_neg += 1
        for w in self.negative_words_weak:
            if w in text:
                weak_neg += 1

        # 2. pattern分级
        for pat in self.positive_patterns:
            if re.search(pat, text):
                strong_pos += 1
        for pat in self.negative_patterns_strong:
            if re.search(pat, text):
                strong_neg += 1
        for pat in self.negative_patterns_weak:
            if re.search(pat, text):
                weak_neg += 1

        # 3. emoji分级
        for e in self.positive_emojis:
            if e in text:
                weak_pos += 1
        for e in self.negative_emojis:
            if e in text:
                weak_neg += 1

        # 4. 叠字/重复表达
        if re.search(r'(绝绝子|冲冲冲|买买买|绝了绝了绝了|callcallcall)', text):
            strong_pos += 1
        if re.search(r'(丑死了|气死了|烂爆了)', text):
            strong_neg += 1

        # 5. 综合得分
        score = 2*strong_pos + weak_pos - 2*strong_neg - weak_neg
        # 归一化（可根据实际最大分数调整）
        norm_score = max(-1, min(1, score/5))

        # 6. 五级标签
        if norm_score >= 0.7:
            label = 'strong_positive'
        elif norm_score >= 0.2:
            label = 'weak_positive'
        elif norm_score > -0.2:
            label = 'neutral'
        elif norm_score > -0.7:
            label = 'weak_negative'
        else:
            label = 'strong_negative'

        return {
            'sentiment_score': norm_score,
            'sentiment_label': label,
            'method': 'fine_grained_dict',
            'strong_positive': strong_pos,
            'weak_positive': weak_pos,
            'strong_negative': strong_neg,
            'weak_negative': weak_neg
        }

    def analyze_sentiment(self, text: str) -> Dict[str, any]:
        """综合情感分析，主输出为分级打分法，保留原有方法结果"""
        if not text or text.strip() == "":
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "confidence": 0.0,
                "method": "empty_text"
            }
        results = {}
        # SnowNLP 分析
        snownlp_result = self.analyze_with_snownlp(text)
        results["snownlp"] = snownlp_result
        # 词典分析
        dict_result = self.analyze_with_dict(text)
        results["dict"] = dict_result
        # 关键词分析
        keyword_result = self.analyze_with_keywords(text)
        results["keywords"] = keyword_result
        # 新增：分级打分法
        fine_result = self.analyze_with_fine_grained_dict(text)
        results["fine_grained_dict"] = fine_result
        # 主输出采用分级打分法
        return {
            "sentiment_score": fine_result["sentiment_score"],
            "sentiment_label": fine_result["sentiment_label"],
            "confidence": 1.0,  # 分级法为主输出，置信度设为1
            "method": "fine_grained_dict",
            "individual_results": results
        }

class BatchSentimentAnalyzer:
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
    
    def analyze_dataframe(self, df: pd.DataFrame, content_column: str = "cleaned_content") -> pd.DataFrame:
        """批量分析DataFrame中的文本"""
        logger.info(f"开始批量情感分析，共 {len(df)} 条数据...")
        
        results = []
        for idx, row in df.iterrows():
            if idx % 100 == 0:
                logger.info(f"处理进度: {idx}/{len(df)}")
            
            text = row[content_column]
            sentiment_result = self.analyzer.analyze_sentiment(text)
            
            results.append({
                "sentiment_score": sentiment_result["sentiment_score"],
                "sentiment_label": sentiment_result["sentiment_label"],
                "sentiment_confidence": sentiment_result["confidence"],
                "sentiment_method": sentiment_result["method"]
            })
        
        # 将结果添加到DataFrame
        result_df = pd.DataFrame(results)
        df_with_sentiment = pd.concat([df, result_df], axis=1)
        
        logger.info("情感分析完成！")
        return df_with_sentiment
    
    def save_analysis_results(self, df: pd.DataFrame, output_path: str):
        """保存分析结果"""
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        # 生成统计报告
        stats = {
            "total_comments": len(df),
            "sentiment_distribution": df['sentiment_label'].value_counts().to_dict(),
            "avg_sentiment_score": df['sentiment_score'].mean(),
            "avg_confidence": df['sentiment_confidence'].mean(),
            "method_distribution": df['sentiment_method'].value_counts().to_dict()
        }
        
        stats_path = output_path.replace('.csv', '_stats.json')
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"分析结果已保存到: {output_path}")
        logger.info(f"统计报告已保存到: {stats_path}")
        
        return stats

def main():
    import argparse
    parser = argparse.ArgumentParser(description="微博评论情感分析器")
    parser.add_argument('--test', action='store_true', help='运行内置测试样例')
    parser.add_argument('--input', type=str, default='data/cleaned/cleaned_weibo_comments.csv', help='输入CSV文件路径')
    parser.add_argument('--output', type=str, default='data/cleaned/with_sentiment.csv', help='输出CSV文件路径')
    parser.add_argument('--content_col', type=str, default='cleaned_content', help='评论内容字段名')
    args = parser.parse_args()

    if args.test:
        # 测试情感分析
        analyzer = SentimentAnalyzer()
        test_texts = [
            "这个LABUBU真的好可爱啊！",
            "垃圾产品，一点都不好",
            "还行吧，一般般",
            "太棒了！666！",
            "无聊死了，没意思",
            "我晕，再冲就剁手！"
        ]
        for text in test_texts:
            result = analyzer.analyze_sentiment(text)
            print(f"文本: {text}")
            print(f"情感得分: {result['sentiment_score']:.3f}")
            print(f"情感标签: {result['sentiment_label']}")
            print(f"置信度: {result['confidence']:.3f}")
            print("-" * 50)
        return

    # 处理实际数据
    import pandas as pd
    batch_analyzer = BatchSentimentAnalyzer()
    print(f"读取数据: {args.input}")
    df = pd.read_csv(args.input)
    print(f"共 {len(df)} 条评论，开始情感分析...")
    df_with_sentiment = batch_analyzer.analyze_dataframe(df, content_column=args.content_col)
    stats = batch_analyzer.save_analysis_results(df_with_sentiment, args.output)
    print(f"分析完成，结果已保存到: {args.output}")
    print(f"统计信息: {stats}")

if __name__ == "__main__":
    main() 