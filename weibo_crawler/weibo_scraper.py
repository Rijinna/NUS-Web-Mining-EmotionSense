#完成可复用的爬虫类
import asyncio
import random
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote
from bs4 import BeautifulSoup

def parse_card(card):
    """提取 card-wrap 微博内容"""
    try:
        mid = card.get("mid", "")

        author_tag = card.select_one("a.name")
        author_name = author_tag.get_text(strip=True) if author_tag else ""

        time_tag = card.select_one("div.from > a")
        post_time = time_tag.get_text(strip=True) if time_tag else ""

        source_tag = card.select("div.from > a")
        source = source_tag[1].get_text(strip=True) if len(source_tag) > 1 else ""

        content_tag = card.select_one("p.txt")
        content_text = content_tag.get_text(separator="", strip=True) if content_tag else ""

        like_tag = card.select_one("span.woo-like-count")
        likes = like_tag.get_text(strip=True) if like_tag else "0"

        comment_tag = card.select_one("a[action-type='feed_list_comment']")
        comments = comment_tag.get_text(strip=True).replace("评论", "") if comment_tag else "0"

        repost_tag = card.select_one("a[action-type='feed_list_forward']")
        reposts = repost_tag.get_text(strip=True).replace("转发", "") if repost_tag else "0"

        return {
            "mid": mid,
            "author": author_name,
            "time": post_time,
            "source": source,
            "text": content_text,
            "likes": likes,
            "comments": comments,
            "reposts": reposts,
        }
    except Exception as e:
        logger.warning(f"解析微博卡片失败: {e}")
        return None

def extract_posts_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="card-wrap")
    logger.info(f"共发现 {len(cards)} 条微博卡片")

    posts = []
    for card in cards:
        post_data = parse_card(card)
        if post_data:
            posts.append(post_data)
    return posts

logger = logging.getLogger(__name__)

@dataclass
class WeiboComment:
    """微博评论数据结构"""
    content: str
    timestamp: str
    user_id: str
    user_name: str
    likes: int
    forwards: int
    comments: int
    post_id: str
    keyword: str

class WeiboScraper:
    """微博爬虫核心类"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        
        # 用户代理池
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
        self.collected_data = []
        
    async def init_browser(self):
        """初始化浏览器"""
        playwright = await async_playwright().start()
        
        # 随机选择用户代理
        user_agent = random.choice(self.user_agents)
        
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'  # 减少被检测为自动化
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            is_mobile=False,
            locale='zh-CN',
            java_script_enabled=True,
            accept_downloads=False,
        )
        
        self.page = await self.context.new_page()
        
        # 加上这个 route 拦截器，打印所有请求路径
        async def intercept_response(route, request):
            if "weibo.com" in request.url:
                logger.debug(f"⚠️ 请求路径：{request.url}")
            await route.continue_()

        await self.page.route("**/*", intercept_response)

        logger.info(f"浏览器初始化完成，使用用户代理: {user_agent}")
        
        # 设置请求拦截，避免加载不必要的资源
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
        
        # 增加一行确认 UA，便于调试
        actual_ua = await self.page.evaluate("() => navigator.userAgent")
        logger.info(f"浏览器初始化完成，使用用户代理: {user_agent}")
        
    async def set_cookies(self, cookies: List[Dict]):
        """设置cookies"""
        if cookies and self.context:
            await self.context.add_cookies(cookies)
            logger.info("Cookies已设置")
            
    async def get_cookies(self) -> List[Dict]:
        """获取当前cookies"""
        if self.context:
            return await self.context.cookies()
        return []
        
    async def search_posts(self, keyword: str, max_pages: int = 5, start_date: str = None, end_date: str = None) -> List[str]:
        """搜索相关帖子，返回帖子URL列表
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大爬取页数
            start_date: 开始日期，格式：'2024-01-01' 或 '2024-12-31'
            end_date: 结束日期，格式：'2025-07-10' 或 '2024-12-31'
        """
        post_urls = []
        
        try:
            # 构建时间范围参数
            if start_date and end_date:
                timescope = f"custom:{start_date}:{end_date}"
                logger.info(f"📅 使用自定义时间范围: {start_date} ~ {end_date}")
            else:
                # 默认使用当前年份
                from datetime import datetime
                current_year = datetime.now().year
                timescope = f"custom:{current_year}-01-01:{current_year}-12-31"
                logger.info(f"📅 使用默认时间范围: {current_year}年全年")
            
            # 搜索页面
            search_url = f"https://s.weibo.com/weibo?q={quote(keyword)}&typeall=1&suball=1&timescope={timescope}&page=1"
            await self.page.goto(search_url)
            await self.page.wait_for_load_state("networkidle")

            # 跳转成功后打印当前 URL
            logger.info(f"🎯 实际跳转到：{self.page.url}")

            await self.page.wait_for_timeout(2000)

            # ✅ 检查 HTML 内容是否加载正确
            html = await self.page.content()

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("div", class_="card-wrap")
            logger.info(f"共找到 {len(cards)} 个 .card-wrap 元素")

            # ✅ 打印前两个样例 card 的内容
            for i, card in enumerate(cards[:2]):
                with open(f"debug_card_{i+1}.html", "w", encoding="utf-8") as f:
                    f.write(card.prettify())
                logger.info(f"已保存样例 card {i+1} 到文件 debug_card_{i+1}.html")

            
            for page_num in range(max_pages):
                logger.info(f"正在爬取关键词 '{keyword}' 的第 {page_num + 1} 页")
                
                # 等待内容加载
                await self.page.wait_for_selector('.card-wrap', timeout=10000)
                
                # 获取帖子链接
                posts = await self.page.locator('.card-wrap').all()
                
                for post in posts:
                    try:
                        link_element = post.locator('.from a').first
                        if await link_element.is_visible():
                            href = await link_element.get_attribute('href')
                            if href:
                                # 某些 href 以 // 开头
                                if href.startswith('//'):
                                    href = 'https:' + href
                                elif href.startswith('/'):
                                    href = 'https://weibo.com' + href
                                post_urls.append(href)
                                logger.debug(f"提取到链接: {href}")
                    except Exception as e:
                        logger.debug(f"处理帖子链接时出错: {e}")
                        continue

                # 滚动到页面底部，加载更多内容
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.random_delay()
                
                # 点击下一页
                next_button = self.page.locator('a[aria-label="下一页"]')
                if await next_button.is_visible():
                    await next_button.click()
                    await self.page.wait_for_load_state("networkidle")
                else:
                    logger.info("没有更多页面了")
                    break
                    
        except Exception as e:
            logger.error(f"搜索帖子时出错: {e}")
            
        logger.info(f"关键词 '{keyword}' 共找到 {len(post_urls)} 个帖子")
        return post_urls
    
    def get_month_dates(self, year: int, month: int) -> tuple:
        """获取指定年份和月份的开始和结束日期
        
        Args:
            year: 年份，如 2024
            month: 月份，1-12
            
        Returns:
            tuple: (start_date, end_date) 格式：('2024-01-01', '2024-01-31')
        """
        if month < 1 or month > 12:
            raise ValueError(f"月份必须是1-12，当前输入：{month}")
        
        # 获取月份天数
        from datetime import datetime
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = (next_month - datetime(year, month, 1)).days
        
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{last_day}"
        
        return start_date, end_date
    
        
    async def extract_comments(self, post_url: str, keyword: str, max_comments: int = 100) -> List[WeiboComment]:
        comments = []
        try:
            await self.page.goto(post_url)
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(3000)
            post_id = post_url.split("/")[-1].split("?")[0]

            # 滚动页面触发评论加载
            for _ in range(10):  # 增加滚动次数
                await self.page.mouse.wheel(0, 5000)
                await self.page.wait_for_timeout(2000)  # 增加等待时间

            # 一级评论选择器
            comment_elements = await self.page.locator('.con1.woo-box-item-flex').all()
            logger.info(f"✅ 使用选择器 .con1.woo-box-item-flex 找到评论数量：{len(comment_elements)}")

            # 二级评论选择器
            sub_comment_elements = await self.page.locator('.item2').all()
            logger.info(f"🔍 检测到全局二级评论数量：{len(sub_comment_elements)}")

            # 提前跳过机制：如果一级和二级评论都为0，直接跳过
            if len(comment_elements) == 0 and len(sub_comment_elements) == 0:
                logger.info(f"⏭️ 帖子 {post_url} 无评论，跳过提取")
                return comments

            # 提取一级评论
            for i, element in enumerate(comment_elements[:max_comments]):
                try:
                    comment = await self.extract_single_comment(element, post_id, keyword)
                    if comment and comment.content.strip():
                        comments.append(comment)
                        logger.debug(f"✅ 成功提取第 {i+1} 条一级评论")
                except Exception as e:
                    logger.debug(f"⚠️ 提取第 {i+1} 条一级评论失败: {e}")
                    continue

            # ====== 统一提取所有二级评论（只做一次）======
            for sub_element in sub_comment_elements:
                try:
                    # 内容
                    text_element = sub_element.locator('.text').first
                    if not await text_element.is_visible():
                        continue
                    text_html = await text_element.inner_html()
                    sub_content = self.extract_text_with_emojis(text_html)

                    # 用户名
                    user_element = sub_element.locator('.text a').first
                    if not await user_element.is_visible():
                        continue
                    sub_user_name = await user_element.text_content()
                    user_href = await user_element.get_attribute("href")
                    sub_user_id = user_href.replace("/u/", "") if user_href and user_href.startswith("/u/") else ""

                    # 时间 - 增强版，处理各种格式
                    sub_timestamp = ""
                    try:
                        time_element = sub_element.locator('.info > div:first-child').first
                        if await time_element.is_visible():
                            full_text = await time_element.text_content()
                            
                            # 清理时间戳文本
                            import re
                            
                            # 方法1：直接按"来自"分割
                            if "来自" in full_text:
                                sub_timestamp = full_text.split("来自")[0].strip()
                            else:
                                sub_timestamp = full_text.strip()
                            
                            # 方法2：用正则表达式精确匹配微博时间格式
                            # 根据你提供的HTML结构，时间格式是：24-12-30 21:10
                            time_patterns = [
                                r'(\d{2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 24-12-30 21:10
                                r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 2024-12-31 22:42
                                r'(\d{1,2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 25-1-1 10:03
                                r'(\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2})',  # 1月1日 10:03
                                r'(\d{1,2}分钟前)',  # 5分钟前
                                r'(\d{1,2}小时前)',  # 2小时前
                                r'(刚刚)',  # 刚刚
                                r'(今天\s+\d{1,2}:\d{2})',  # 今天 10:03
                                r'(昨天\s+\d{1,2}:\d{2})',  # 昨天 10:03
                            ]
                            
                            for pattern in time_patterns:
                                match = re.search(pattern, sub_timestamp)
                                if match:
                                    sub_timestamp = match.group(1)
                                    break
                            
                            # 最终清理：只保留时间相关字符
                            sub_timestamp = re.sub(r'[^\d\-\s:月日分钟小时前刚刚今天昨天]', '', sub_timestamp).strip()
                            
                            # 验证时间戳格式
                            if not sub_timestamp or len(sub_timestamp) < 3:
                                logger.debug(f"⚠️ 提取到的二级评论时间戳可能无效: '{sub_timestamp}'")
                    except Exception as e:
                        logger.debug(f"⚠️ 提取二级评论时间戳出错: {e}")
                        pass

                    # 点赞数
                    likes = 0
                    try:
                        like_element = sub_element.locator('.woo-like-main').first
                        if await like_element.is_visible():
                            like_text_element = like_element.locator('.woo-like-count, span:not(.woo-like-iconWrap)')
                            if await like_text_element.count() > 0:
                                like_text = await like_text_element.first.text_content()
                                likes = int(like_text.strip()) if like_text.strip().isdigit() else 0
                    except Exception as e:
                        logger.debug(f"⚠️ 提取二级评论点赞数出错: {e}")

                    # 清理二级评论内容：去掉用户名和"回复@"部分
                    cleaned_content = sub_content.strip()
                    
                    # 去掉"回复@用户名"部分
                    import re
                    cleaned_content = re.sub(r'回复@[^:：\s]+[:：]\s*', '', cleaned_content)
                    
                    # 去掉用户名部分（如果还有的话）
                    if ":" in cleaned_content:
                        cleaned_content = cleaned_content.split(":", 1)[1].strip()
                    elif "：" in cleaned_content:
                        cleaned_content = cleaned_content.split("：", 1)[1].strip()
                    
                    # 过滤掉明显不是评论的内容
                    if any(keyword in cleaned_content for keyword in ['共', '条回复', '展开', '收起', '举报']):
                        logger.debug(f"⚠️ 跳过非评论内容: {cleaned_content}")
                        continue
                    
                    # 构造 WeiboComment 对象
                    sub_comment = WeiboComment(
                        content=cleaned_content,
                        timestamp=sub_timestamp.strip(),
                        user_id=sub_user_id,
                        user_name=sub_user_name.strip(),
                        likes=likes,
                        forwards=0,
                        comments=0,
                        post_id=post_id,
                        keyword=keyword
                    )
                    comments.append(sub_comment)
                    logger.debug(f"✅ 成功提取二级评论: 用户={sub_user_name}, 内容={cleaned_content[:30]}")

                except Exception as e:
                    logger.debug(f"⚠️ 提取单条二级评论失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"💥 详情页提取评论失败 {post_url}: {e}")
            
        logger.info(f"📊 从帖子 {post_url} 提取了 {len(comments)} 条评论")
        return comments
        
    async def extract_single_comment(self, comment_element, post_id: str, keyword: str) -> Optional[WeiboComment]:
        try:
            # 提取评论内容 - 增强版，处理lazy load和innerHTML
            content = ""
            try:
                # 首先尝试获取.text元素的innerHTML，这样可以包含表情
                text_element = comment_element.locator(".text").first
                if await text_element.is_visible():
                    # 获取innerHTML而不是text_content，这样可以包含表情
                    text_html = await text_element.inner_html()
                    if text_html:
                        # 使用BeautifulSoup解析HTML，提取文本和表情
                        content = self.extract_text_with_emojis(text_html)
                        # 去掉用户名部分，提取冒号后的内容
                        if ":" in content:
                            content = content.split(":", 1)[1].strip()
                        
                # 如果innerHTML方法失败，回退到text_content方法
                if not content:
                    content_selectors = [
                        ".text span:last-child",  # 最后一个span通常是评论内容
                        ".text > span:last-of-type",  # 直接子元素的最后一个span
                        ".text span:not([class])",  # 没有class的span
                        ".text span"  # 所有span作为备选
                    ]
                    
                    for selector in content_selectors:
                        try:
                            content_element = comment_element.locator(selector).first
                            if await content_element.is_visible():
                                content = (await content_element.text_content()).strip()
                                if content and not content.startswith("来自"):  # 过滤掉"来自XXX"
                                    break
                        except:
                            continue
                            
                    # 如果上面都没获取到，尝试获取整个.text的内容然后处理
                    if not content:
                        if await text_element.is_visible():
                            full_text = await text_element.text_content()
                            # 去掉用户名部分，提取冒号后的内容
                            if ":" in full_text:
                                content = full_text.split(":", 1)[1].strip()
                            else:
                                content = full_text.strip()
                                
            except Exception as e:
                logger.debug(f"提取评论内容时出错: {e}")
                pass
                
            if not content:
                logger.debug("❌ 评论内容为空，跳过")
                return None

            # 清理评论内容：去掉用户名部分
            original_content = content
            import re
            
            # 去掉"回复@用户名"部分
            content = re.sub(r'回复@[^:：\s]+[:：]\s*', '', content)
            
            # 去掉用户名部分（支持多种格式）
            if ":" in content:
                content = content.split(":", 1)[1].strip()
            elif "：" in content:
                content = content.split("：", 1)[1].strip()
            
            # 如果清理后内容为空，使用原始内容
            if not content:
                content = original_content
            
            # 过滤掉明显不是评论的内容
            if any(keyword in content for keyword in ['共', '条回复', '展开', '收起', '举报']):
                logger.debug(f"⚠️ 跳过非评论内容: {content}")
                return None

            # 提取用户名和链接 - 更精确的选择器
            user_name = ""
            user_id = ""
            try:
                # 根据HTML结构，第一个a标签是用户链接
                user_element = comment_element.locator(".text a[href^='/u/']").first
                if await user_element.is_visible():
                    user_name = (await user_element.text_content()).strip()
                    user_href = await user_element.get_attribute("href") or ""
                    # 提取用户ID
                    if user_href.startswith("/u/"):
                        user_id = user_href.replace("/u/", "")
            except Exception as e:
                logger.debug(f"提取用户信息时出错: {e}")
                pass

            # 提取时间戳 - 根据实际HTML结构优化
            timestamp = ""
            try:
                time_element = comment_element.locator(".info > div:first-child").first
                if await time_element.is_visible():
                    full_text = await time_element.text_content()
                    
                    # 清理时间戳文本
                    import re
                    
                    # 方法1：直接按"来自"分割（最可靠的方法）
                    if "来自" in full_text:
                        timestamp = full_text.split("来自")[0].strip()
                    else:
                        timestamp = full_text.strip()
                    
                    # 方法2：用正则表达式精确匹配微博时间格式
                    # 根据你提供的HTML结构，时间格式是：24-12-30 21:10
                    time_patterns = [
                        r'(\d{2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 24-12-30 21:10
                        r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 2024-12-31 22:42
                        r'(\d{1,2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 25-1-1 10:03
                        r'(\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2})',  # 1月1日 10:03
                        r'(\d{1,2}分钟前)',  # 5分钟前
                        r'(\d{1,2}小时前)',  # 2小时前
                        r'(刚刚)',  # 刚刚
                        r'(今天\s+\d{1,2}:\d{2})',  # 今天 10:03
                        r'(昨天\s+\d{1,2}:\d{2})',  # 昨天 10:03
                    ]
                    
                    for pattern in time_patterns:
                        match = re.search(pattern, timestamp)
                        if match:
                            timestamp = match.group(1)
                            break
                    
                    # 最终清理：只保留时间相关字符
                    timestamp = re.sub(r'[^\d\-\s:月日分钟小时前刚刚今天昨天]', '', timestamp).strip()
                    
                    # 验证时间戳格式
                    if not timestamp or len(timestamp) < 3:
                        logger.debug(f"⚠️ 提取到的时间戳可能无效: '{timestamp}'")
                    
            except Exception as e:
                logger.debug(f"提取时间戳时出错: {e}")
                pass

            # 提取点赞数 - 修改选择器
            likes = 0
            try:
                # 根据HTML结构，点赞按钮在IconList_likebox_23Rt_类中
                like_element = comment_element.locator(".woo-like-main").first
                if await like_element.is_visible():
                    # 查找点赞数文本，可能在按钮内部或附近
                    like_text_element = like_element.locator(".woo-like-count, span:not(.woo-like-iconWrap)")
                    if await like_text_element.count() > 0:
                        like_text = await like_text_element.first.text_content()
                        likes = int(like_text.strip()) if like_text.strip().isdigit() else 0
            except Exception as e:
                logger.debug(f"提取点赞数时出错: {e}")
                pass

            # 转发和评论数未知，设为 0
            forwards = 0
            comment_count = 0

            logger.debug(f"✅ 成功提取评论: 用户={user_name}, 内容={content[:50]}...")
            
            return WeiboComment(
                content=content,
                timestamp=timestamp,
                user_id=user_id,
                user_name=user_name,
                likes=likes,
                forwards=forwards,
                comments=comment_count,
                post_id=post_id,
                keyword=keyword
            )
            
        except Exception as e:
            logger.debug(f"❌ 提取单条评论时出错: {e}")
            return None
            
    async def extract_interaction_count(self, element, text_type: str) -> int:
        """提取互动数量"""
        try:
            interaction_element = element.locator(f'a:has-text("{text_type}")').first
            if await interaction_element.is_visible():
                text = await interaction_element.text_content()
                # 提取数字
                import re
                numbers = re.findall(r'\d+', text)
                return int(numbers[0]) if numbers else 0
            return 0
        except:
            return 0
            
    async def random_delay(self, min_delay: float = 1, max_delay: float = 3):
        """随机延迟，避免被检测"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            logger.info("浏览器已关闭")
            
    def add_comments(self, comments: List[WeiboComment]):
        """添加评论到收集数据中"""
        self.collected_data.extend(comments)
        
    def get_collected_data(self) -> List[WeiboComment]:
        """获取收集到的数据"""
        return self.collected_data
        
    def clear_collected_data(self):
        """清空收集的数据"""
        self.collected_data.clear()
        
    async def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            await self.page.goto("https://weibo.com")
            await self.page.wait_for_load_state("networkidle")

            logger.info(f"🎯实际访问的页面地址: {self.page.url}")
            
            # 检查是否有登录按钮
            login_button = self.page.locator('a[href*="login"]')
            if await login_button.is_visible():
                logger.info("用户未登录")
                return False
            else:
                logger.info("用户已登录")
                return True
        except Exception as e:
            logger.error(f"检查登录状态时出错: {e}")
            return False

    @staticmethod
    def extract_text_with_emojis(html):
        from bs4 import BeautifulSoup, NavigableString
        import re

        soup = BeautifulSoup(html, 'html.parser')
        result = []

        def extract_text_recursive(element):
            if isinstance(element, NavigableString):
                return str(element)
            elif element.name == 'img':
                return element.get('alt') or element.get('title') or ''
            elif element.name == 'br':
                return '\n'
            else:
                return ''.join(extract_text_recursive(child) for child in element.children)

        # 处理所有根元素
        for element in soup.children:
            result.append(extract_text_recursive(element))

        # 拼接并清洗空白
        text = ''.join(result)
        text = re.sub(r'[ \t\u3000]+', ' ', text)  # 去除中文空格、tab
        text = re.sub(r'\n+', '\n', text)         # 合并多余换行
        return text.strip()