#调试版本评论提取器
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from weibo_scraper import WeiboScraper
from cookie_loader import CookieManager, WeiboLogin
from utils import DataSaver

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_extract_comments(self, post_url: str, keyword: str, max_comments: int = 100):
    """调试版本的评论提取方法"""
    comments = []
    try:
        await self.page.goto(post_url)
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(3000)
        post_id = post_url.split("/")[-1].split("?")[0]

        # 滚动页面触发评论加载
        for _ in range(5):  # 减少滚动次数
            await self.page.mouse.wheel(0, 3000)
            await self.page.wait_for_timeout(1000)

        # 一级评论选择器
        comment_elements = await self.page.locator('.con1.woo-box-item-flex').all()
        logger.info(f"✅ 使用选择器 .con1.woo-box-item-flex 找到评论数量：{len(comment_elements)}")

        # 提取一级评论
        for i, element in enumerate(comment_elements[:max_comments]):
            try:
                logger.debug(f"🔍 开始提取第 {i+1} 条一级评论")
                
                # 调试：获取评论元素的HTML
                element_html = await element.inner_html()
                logger.debug(f"评论元素HTML: {element_html[:200]}...")
                
                comment = await debug_extract_single_comment(self, element, post_id, keyword)
                if comment and comment.content.strip():
                    comments.append(comment)
                    logger.info(f"✅ 成功提取第 {i+1} 条一级评论: {comment.content[:50]}...")
                else:
                    logger.warning(f"❌ 第 {i+1} 条一级评论提取失败或内容为空")
            except Exception as e:
                logger.error(f"⚠️ 提取第 {i+1} 条一级评论失败: {e}")
                continue

        # 二级评论
        sub_comment_elements = await self.page.locator('.item2').all()
        logger.info(f"🔍 检测到全局二级评论数量：{len(sub_comment_elements)}")

        for i, sub_element in enumerate(sub_comment_elements):
            try:
                logger.debug(f"🔍 开始提取第 {i+1} 条二级评论")
                
                # 调试：获取二级评论元素的HTML
                sub_element_html = await sub_element.inner_html()
                logger.debug(f"二级评论元素HTML: {sub_element_html[:200]}...")
                
                # 内容
                text_element = sub_element.locator('.text').first
                if not await text_element.is_visible():
                    logger.debug("二级评论文本元素不可见")
                    continue
                    
                text_html = await text_element.inner_html()
                logger.debug(f"二级评论文本HTML: {text_html}")
                
                # 直接在这里定义extract_text_with_emojis函数
                def extract_text_with_emojis_local(html):
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
                
                sub_content = extract_text_with_emojis_local(text_html)
                logger.debug(f"提取的二级评论内容: {sub_content}")

                if not sub_content.strip():
                    logger.warning(f"❌ 第 {i+1} 条二级评论内容为空")
                    continue

                # 用户名
                user_element = sub_element.locator('.text a').first
                if not await user_element.is_visible():
                    logger.debug("二级评论用户元素不可见")
                    continue
                    
                sub_user_name = await user_element.text_content()
                user_href = await user_element.get_attribute("href")
                sub_user_id = user_href.replace("/u/", "") if user_href and user_href.startswith("/u/") else ""

                # 时间
                sub_timestamp = ""
                try:
                    time_element = sub_element.locator('.info > div:first-child').first
                    if await time_element.is_visible():
                        full_text = await time_element.text_content()
                        logger.debug(f"二级评论时间原始文本: {full_text}")
                        
                        if "来自" in full_text:
                            sub_timestamp = full_text.split("来自")[0].strip()
                        else:
                            sub_timestamp = full_text.strip()
                            
                        logger.debug(f"二级评论提取时间: {sub_timestamp}")
                except Exception as e:
                    logger.debug(f"提取二级评论时间出错: {e}")

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
                    logger.debug(f"提取二级评论点赞数出错: {e}")

                # 构造 WeiboComment 对象
                from weibo_scraper import WeiboComment
                sub_comment = WeiboComment(
                    content=sub_content.strip(),
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
                logger.info(f"✅ 成功提取二级评论: 用户={sub_user_name}, 内容={sub_content[:30]}")

            except Exception as e:
                logger.error(f"⚠️ 提取第 {i+1} 条二级评论失败: {e}")
                continue

    except Exception as e:
        logger.error(f"💥 详情页提取评论失败 {post_url}: {e}")

    logger.info(f"📊 从帖子 {post_url} 提取了 {len(comments)} 条评论")
    return comments

async def debug_extract_single_comment(self, comment_element, post_id: str, keyword: str):
    """调试版本的单条评论提取"""
    try:
        logger.debug("🔍 开始提取单条评论")
        
        # 提取评论内容
        content = ""
        try:
            text_element = comment_element.locator(".text").first
            if await text_element.is_visible():
                # 获取innerHTML
                text_html = await text_element.inner_html()
                logger.debug(f"评论文本HTML: {text_html}")
                
                if text_html:
                    # 直接在这里定义extract_text_with_emojis函数
                    def extract_text_with_emojis_local(html):
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
                    
                    content = extract_text_with_emojis_local(text_html)
                    logger.debug(f"提取的评论内容: {content}")
                    
                    # 去掉用户名部分
                    if ":" in content:
                        content = content.split(":", 1)[1].strip()
                        logger.debug(f"去掉用户名后的内容: {content}")
                        
            # 如果innerHTML方法失败，尝试其他方法
            if not content:
                logger.debug("innerHTML方法失败，尝试text_content方法")
                content_selectors = [
                    ".text span:last-child",
                    ".text > span:last-of-type", 
                    ".text span:not([class])",
                    ".text span"
                ]
                
                for selector in content_selectors:
                    try:
                        content_element = comment_element.locator(selector).first
                        if await content_element.is_visible():
                            content = (await content_element.text_content()).strip()
                            logger.debug(f"使用选择器 {selector} 提取内容: {content}")
                            if content and not content.startswith("来自"):
                                break
                    except:
                        continue
                        
                # 最后尝试获取整个.text的内容
                if not content:
                    if await text_element.is_visible():
                        full_text = await text_element.text_content()
                        logger.debug(f"整个text元素内容: {full_text}")
                        if ":" in full_text:
                            content = full_text.split(":", 1)[1].strip()
                        else:
                            content = full_text.strip()
                            
        except Exception as e:
            logger.error(f"提取评论内容时出错: {e}")
            
        if not content:
            logger.warning("❌ 评论内容为空")
            return None

        # 提取用户名
        user_name = ""
        user_id = ""
        try:
            user_element = comment_element.locator(".text a[href^='/u/']").first
            if await user_element.is_visible():
                user_name = (await user_element.text_content()).strip()
                user_href = await user_element.get_attribute("href") or ""
                if user_href.startswith("/u/"):
                    user_id = user_href.replace("/u/", "")
                logger.debug(f"提取用户名: {user_name}, 用户ID: {user_id}")
        except Exception as e:
            logger.error(f"提取用户信息时出错: {e}")

        # 提取时间戳
        timestamp = ""
        try:
            time_element = comment_element.locator(".info > div:first-child").first
            if await time_element.is_visible():
                full_text = await time_element.text_content()
                logger.debug(f"时间原始文本: {full_text}")
                
                if "来自" in full_text:
                    timestamp = full_text.split("来自")[0].strip()
                else:
                    timestamp = full_text.strip()
                    
                logger.debug(f"提取时间: {timestamp}")
        except Exception as e:
            logger.error(f"提取时间戳时出错: {e}")

        # 提取点赞数
        likes = 0
        try:
            like_element = comment_element.locator(".woo-like-main").first
            if await like_element.is_visible():
                like_text_element = like_element.locator(".woo-like-count, span:not(.woo-like-iconWrap)")
                if await like_text_element.count() > 0:
                    like_text = await like_text_element.first.text_content()
                    likes = int(like_text.strip()) if like_text.strip().isdigit() else 0
                    logger.debug(f"提取点赞数: {likes}")
        except Exception as e:
            logger.error(f"提取点赞数时出错: {e}")

        logger.debug(f"✅ 成功提取评论: 用户={user_name}, 内容={content[:50]}...")

        from weibo_scraper import WeiboComment
        return WeiboComment(
            content=content,
            timestamp=timestamp,
            user_id=user_id,
            user_name=user_name,
            likes=likes,
            forwards=0,
            comments=0,
            post_id=post_id,
            keyword=keyword
        )

    except Exception as e:
        logger.error(f"❌ 提取单条评论时出错: {e}")
        return None

async def debug_test():
    """调试测试函数"""
    scraper = WeiboScraper(headless=False)
    await scraper.init_browser()
    
    # 测试一个具体的帖子
    test_url = "https://weibo.com/3872639122/P9JTb4iJ6?refer_flag=1001030103_"
    
    # 创建extract_text_with_emojis函数
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
    
    # 替换方法
    scraper.extract_comments = lambda post_url, keyword, max_comments: debug_extract_comments(scraper, post_url, keyword, max_comments)
    scraper.extract_single_comment = lambda element, post_id, keyword: debug_extract_single_comment(scraper, element, post_id, keyword)
    
    comments = await scraper.extract_comments(test_url, "LABUBU", 10)
    
    print(f"\n最终结果: 提取到 {len(comments)} 条评论")
    for i, comment in enumerate(comments):
        print(f"评论 {i+1}: {comment.content[:100]}...")
    
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(debug_test()) 