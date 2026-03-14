import json
import csv
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from weibo_scraper import WeiboComment

logger = logging.getLogger(__name__)

class DataSaver:
    """数据保存器"""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_filename(self, prefix: str, extension: str) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}.{extension}"

    def save_to_csv(self, comments: List[WeiboComment], filename: str = None) -> str:
        if not filename:
            filename = self.generate_filename("weibo_comments", "csv")
        filepath = self.output_dir / filename

        try:
            # 使用UTF-8-BOM编码，确保Excel正确识别中文
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['content', 'timestamp', 'user_id', 'user_name', 'likes', 'forwards', 'comments', 'post_id', 'keyword']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for comment in comments:
                    # 确保所有字段都是字符串类型，避免编码问题
                    row = {}
                    for field in fieldnames:
                        value = getattr(comment, field, '')
                        row[field] = str(value) if value is not None else ''
                    writer.writerow(row)
            logger.info(f"数据已保存到 {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"保存CSV文件失败: {e}")
            return None

    def save_to_json(self, comments: List[WeiboComment], filename: str = None) -> str:
        if not filename:
            filename = self.generate_filename("weibo_comments", "json")
        filepath = self.output_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump([comment.__dict__ for comment in comments], jsonfile, ensure_ascii=False, indent=2)
            logger.info(f"数据已保存到 {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"保存JSON文件失败: {e}")
            return None

    def save_statistics(self, comments: List[WeiboComment], filename: str = None) -> str:
        if not filename:
            filename = self.generate_filename("weibo_statistics", "json")
        filepath = self.output_dir / filename

        try:
            stats = self.calculate_statistics(comments)
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(stats, jsonfile, ensure_ascii=False, indent=2)
            logger.info(f"统计信息已保存到 {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"保存统计信息失败: {e}")
            return None

    def calculate_statistics(self, comments: List[WeiboComment]) -> Dict:
        total_comments = len(comments)
        total_likes = sum(c.likes for c in comments)
        total_forwards = sum(c.forwards for c in comments)

        keyword_stats = {}
        for c in comments:
            if c.keyword not in keyword_stats:
                keyword_stats[c.keyword] = {'count': 0, 'likes': 0, 'forwards': 0, 'comments': 0}
            keyword_stats[c.keyword]['count'] += 1
            keyword_stats[c.keyword]['likes'] += c.likes
            keyword_stats[c.keyword]['forwards'] += c.forwards
            keyword_stats[c.keyword]['comments'] += c.comments

        user_stats = {}
        for c in comments:
            if c.user_name not in user_stats:
                user_stats[c.user_name] = {'comment_count': 0, 'total_likes': 0, 'total_forwards': 0}
            user_stats[c.user_name]['comment_count'] += 1
            user_stats[c.user_name]['total_likes'] += c.likes
            user_stats[c.user_name]['total_forwards'] += c.forwards

        top_users = dict(sorted(user_stats.items(), key=lambda x: x[1]['comment_count'], reverse=True)[:10])

        return {
            'basic_stats': {
                'total_comments': total_comments,
                'total_likes': total_likes,
                'total_forwards': total_forwards,
                'average_likes_per_comment': total_likes / total_comments if total_comments else 0,
                'average_forwards_per_comment': total_forwards / total_comments if total_comments else 0
            },
            'keyword_stats': keyword_stats,
            'top_users': top_users,
            'generated_at': datetime.now().isoformat()
        }

class DataValidator:
    @staticmethod
    def validate_comment(comment: WeiboComment) -> bool:
        if not comment:
            return False
        required_fields = ['content', 'user_name', 'post_id', 'keyword']
        for field in required_fields:
            if not getattr(comment, field, None):
                return False
        return all(isinstance(getattr(comment, f), int) and getattr(comment, f) >= 0 for f in ['likes', 'forwards', 'comments'])

    @staticmethod
    def clean_comment_content(content: str) -> str:
        import re
        content = ' '.join(content.split())
        return re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:"\'()（）【】「」《》\-]', '', content).strip()

    @staticmethod
    def filter_valid_comments(comments: List[WeiboComment]) -> List[WeiboComment]:
        valid = []
        for c in comments:
            if DataValidator.validate_comment(c):
                c.content = DataValidator.clean_comment_content(c.content)
                valid.append(c)
        return valid

class FileManager:
    @staticmethod
    def ensure_directory(path: str) -> Path:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def list_files(directory: str, extension: str = None) -> List[str]:
        path = Path(directory)
        if not path.exists():
            return []
        return [str(f) for f in sorted(path.glob(f"*.{extension}" if extension else "*"))]

    @staticmethod
    def delete_old_files(directory: str, max_files: int = 10):
        files = FileManager.list_files(directory)
        if len(files) > max_files:
            for f in files[:-max_files]:
                try:
                    os.remove(f)
                except OSError as e:
                    logger.error(f"删除文件失败: {e}")
