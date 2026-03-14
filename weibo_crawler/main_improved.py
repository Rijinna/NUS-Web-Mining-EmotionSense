#改进的主执行脚本，支持按时间段均匀爬取
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
import json
import sys
import os

from weibo_scraper import WeiboScraper
from cookie_loader import CookieManager, WeiboLogin
from utils import DataSaver, DataValidator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_time_periods(start_date: str, end_date: str, period_days: int = 30):
    """生成时间段列表，每个时间段period_days天"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    periods = []
    current = start
    
    while current < end:
        period_end = min(current + timedelta(days=period_days), end)
        periods.append((
            current.strftime("%Y-%m-%d"),
            period_end.strftime("%Y-%m-%d")
        ))
        current = period_end + timedelta(days=1)
    
    return periods

async def run_crawler_by_periods(
    keyword_file: str = "../data/keywords.txt",
    cookie_file: str = "../data/weibo_cookies.json",
    output_dir: str = "../data/raw",
    start_date: str = "2024-12-31",
    end_date: str = "2025-07-10",
    period_days: int = 30,  # 每个时间段30天
    max_pages_per_period: int = 30,  # 每个时间段最多3页
    max_comments: int = 50,
    target_comments_per_day: int = 10,  # 每天目标评论数
    start_period_idx: int = 0,
    end_period_idx: int = None
):
    """按时间段均匀爬取数据"""
    
    # Step 1: 读取关键词
    keywords = []
    try:
        with open(keyword_file, 'r', encoding='utf-8') as f:
            keywords = [line.strip() for line in f if line.strip()]
        logger.info(f"加载关键词：{keywords}")
    except Exception as e:
        logger.error(f"关键词文件加载失败: {e}")
        return

    # Step 2: 生成时间段
    periods = generate_time_periods(start_date, end_date, period_days)
    if end_period_idx is None:
        end_period_idx = len(periods)
    logger.info(f"本次将处理 period {start_period_idx+1} 到 {end_period_idx} 共 {end_period_idx-start_period_idx} 个 period")
    for i, (start, end) in enumerate(periods):
        logger.info(f"  时间段 {i+1}: {start} 到 {end}")

    # Step 3: 初始化爬虫和 cookies
    scraper = WeiboScraper(headless=False)
    await scraper.init_browser()

    # Step 4: 加载并注入 Cookie
    try:
        cookie_manager = CookieManager(cookie_file=cookie_file)
        login_handler = WeiboLogin(scraper, cookie_manager)
        await login_handler.ensure_login()
    except Exception as e:
        logger.warning(f"Cookie 加载或登录失败：{e}")

    # Step 5: 按时间段爬取数据
    all_comments = []
    period_stats = []
    
    for period_idx, (period_start, period_end) in enumerate(periods):
        if period_idx < start_period_idx or period_idx >= end_period_idx:
            continue  # 跳过不在本批次的 period

        period_filename = f"period_{period_idx+1}_{period_start}_{period_end}.csv"
        period_path = os.path.join(output_dir, period_filename)
        if os.path.exists(period_path):
            logger.info(f"period {period_idx+1} 已存在，跳过")
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"开始处理 period {period_idx+1}: {period_start} 到 {period_end}")
        logger.info(f"{'='*50}")
        
        period_comments = []
        
        for keyword_idx, keyword in enumerate(keywords):
            logger.info(f"处理关键词 {keyword_idx + 1}/{len(keywords)}: {keyword}")
            
            try:
                post_urls = await scraper.search_posts(
                    keyword=keyword, 
                    max_pages=max_pages_per_period,
                    start_date=period_start,
                    end_date=period_end
                )
                
                logger.info(f"关键词 '{keyword}' 在时间段 {period_start}-{period_end} 找到 {len(post_urls)} 个帖子")
                
                for i, post_url in enumerate(post_urls):
                    logger.info(f"处理帖子 {i+1}/{len(post_urls)}: {post_url}")
                    comments = await scraper.extract_comments(post_url, keyword, max_comments=max_comments)
                    
                    if len(comments) > 0:
                        period_comments.extend(comments)
                        logger.info(f"✅ 从帖子提取了 {len(comments)} 条评论")
                    else:
                        logger.info(f"⏭️ 帖子无评论，已跳过")
                    
                    # 添加随机延迟避免被反爬
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"处理关键词 '{keyword}' 时出错: {e}")
                continue
        
        # 统计当前时间段的数据
        period_days_count = (datetime.strptime(period_end, "%Y-%m-%d") - 
                           datetime.strptime(period_start, "%Y-%m-%d")).days + 1
        comments_per_day = len(period_comments) / period_days_count if period_days_count > 0 else 0
        
        period_stats.append({
            "period": f"{period_start} 到 {period_end}",
            "total_comments": len(period_comments),
            "days": period_days_count,
            "comments_per_day": round(comments_per_day, 2),
            "target_per_day": target_comments_per_day,
            "achievement_rate": round(comments_per_day / target_comments_per_day * 100, 2) if target_comments_per_day > 0 else 0
        })
        
        logger.info(f"period {period_idx+1} 统计:")
        logger.info(f"  总评论数: {len(period_comments)}")
        logger.info(f"  天数: {period_days_count}")
        logger.info(f"  日均评论数: {comments_per_day:.2f}")
        logger.info(f"  目标达成率: {period_stats[-1]['achievement_rate']}%")
        
        all_comments.extend(period_comments)
        
        # 保存period数据
        if period_comments:
            temp_saver = DataSaver(output_dir=output_dir)
            temp_saver.save_to_csv(period_comments, filename=period_filename)
            logger.info(f"period {period_idx+1} 已保存到 {period_path}")
        else:
            logger.info(f"period {period_idx+1} 无评论，未保存")
    
    # Step 6: 最终数据清洗和保存
    logger.info(f"\n{'='*50}")
    logger.info(f"爬取完成！总共收集 {len(all_comments)} 条评论")
    logger.info(f"{'='*50}")
    
    valid_comments = DataValidator.filter_valid_comments(all_comments)
    logger.info(f"有效评论数: {len(valid_comments)}")

    # Step 7: 保存数据和统计
    saver = DataSaver(output_dir=output_dir)
    saver.save_to_csv(valid_comments)
    saver.save_to_json(valid_comments)
    saver.save_statistics(valid_comments)
    
    # 保存时间段统计
    with open(f"{output_dir}/period_statistics.json", 'w', encoding='utf-8') as f:
        json.dump(period_stats, f, ensure_ascii=False, indent=2)
    
    # 打印时间段统计
    logger.info("\n时间段统计:")
    for stat in period_stats:
        logger.info(f"  {stat['period']}: {stat['total_comments']} 条评论, "
                   f"日均 {stat['comments_per_day']} 条, "
                   f"达成率 {stat['achievement_rate']}%")

    # 关闭浏览器
    await scraper.close()

if __name__ == "__main__":
    # 设置参数
    start_date = "2024-04-01"
    end_date = "2025-07-16"
    period_days = 2
    max_pages_per_period = 30
    target_comments_per_day = 10
    output_dir = "../data/raw"
    # 命令行参数支持
    start_period_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_period_idx = int(sys.argv[2]) if len(sys.argv) > 2 else None
    logger.info(f"开始按时间段均匀爬取")
    logger.info(f"时间范围: {start_date} 到 {end_date}")
    logger.info(f"时间段长度: {period_days} 天")
    logger.info(f"每个时间段最多爬取: {max_pages_per_period} 页")
    logger.info(f"每天目标评论数: {target_comments_per_day} 条")
    logger.info(f"本次 period 范围: {start_period_idx+1} ~ {end_period_idx if end_period_idx is not None else '全部'}")
    asyncio.run(run_crawler_by_periods(
        start_date=start_date,
        end_date=end_date,
        period_days=period_days,
        max_pages_per_period=max_pages_per_period,
        target_comments_per_day=target_comments_per_day,
        output_dir=output_dir,
        start_period_idx=start_period_idx,
        end_period_idx=end_period_idx
    )) 