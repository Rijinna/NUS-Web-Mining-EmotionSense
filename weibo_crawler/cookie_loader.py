# 加载微博 cookies
import json
import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class CookieManager:
    """Cookie管理器"""
    
    def __init__(self, cookie_file: str = "weibo_cookies.json"):
        self.cookie_file = Path(cookie_file)
        self.cookies = []
        
    def load_cookies(self) -> List[Dict]:
        """从文件加载cookies"""
        try:
            if self.cookie_file.exists():
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    self.cookies = json.load(f)
                logger.info(f"已加载 {len(self.cookies)} 个cookies")
                return self.cookies
            else:
                logger.warning(f"Cookie文件 {self.cookie_file} 不存在")
                return []
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")
            return []
            
    def save_cookies(self, cookies: List[Dict]):
        """保存cookies到文件"""
        try:
            self.cookies = cookies
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(cookies)} 个cookies到 {self.cookie_file}")
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
            
    def is_cookie_valid(self, cookie: Dict) -> bool:
        """检查cookie是否有效"""
        required_fields = ['name', 'value', 'domain']
        return all(field in cookie for field in required_fields)
        
    def filter_valid_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """过滤有效的cookies"""
        valid_cookies = []
        for cookie in cookies:
            if self.is_cookie_valid(cookie):
                valid_cookies.append(cookie)
            else:
                logger.warning(f"发现无效cookie: {cookie}")
        return valid_cookies
        
    def clear_cookies(self):
        """清空cookies"""
        self.cookies = []
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            logger.info("已清空cookies")
            
    def get_cookies(self) -> List[Dict]:
        """获取当前cookies"""
        return self.cookies
        
    def update_cookies(self, new_cookies: List[Dict]):
        """更新cookies"""
        if new_cookies:
            valid_cookies = self.filter_valid_cookies(new_cookies)
            self.save_cookies(valid_cookies)
            
    def has_cookies(self) -> bool:
        """检查是否有cookies"""
        return len(self.cookies) > 0

class WeiboLogin:
    """微博登录管理器"""
    
    def __init__(self, scraper, cookie_manager: CookieManager):
        self.scraper = scraper
        self.cookie_manager = cookie_manager
        
    async def login_with_cookies(self) -> bool:
        """使用cookies登录"""
        try:
            cookies = self.cookie_manager.load_cookies()
            if not cookies:
                logger.warning("没有找到有效的cookies")
                return False
                
            # 设置cookies
            await self.scraper.set_cookies(cookies)
            
            # 检查登录状态
            login_status = await self.scraper.check_login_status()
            if login_status:
                logger.info("Cookie登录成功")
                return True
            else:
                logger.warning("Cookie登录失败，可能已过期")
                return False
                
        except Exception as e:
            logger.error(f"Cookie登录失败: {e}")
            return False
            
    async def manual_login(self, username: str = None, password: str = None) -> bool:
        """手动登录"""
        try:
            await self.scraper.page.goto("https://weibo.com/login.php")
            await self.scraper.page.wait_for_load_state("networkidle")
            
            if username and password:
                # 自动填写用户名和密码
                await self.scraper.page.fill('input[name="username"]', username)
                await self.scraper.page.fill('input[name="password"]', password)
                
                # 点击登录按钮
                await self.scraper.page.click('a[node-type="submitBtn"]')
                await self.scraper.page.wait_for_load_state("networkidle")
                
                # 检查是否需要验证码
                if await self.scraper.page.locator('.code').is_visible():
                    logger.warning("需要验证码，请手动处理")
                    await self.scraper.page.pause()  # 暂停等待手动处理
                    
            else:
                logger.info("请手动登录微博")
                await self.scraper.page.pause()  # 暂停等待手动登录
                
            # 验证登录状态
            login_status = await self.scraper.check_login_status()
            if login_status:
                # 保存cookies
                cookies = await self.scraper.get_cookies()
                self.cookie_manager.save_cookies(cookies)
                logger.info("手动登录成功，cookies已保存")
                return True
            else:
                logger.error("手动登录失败")
                return False
                
        except Exception as e:
            logger.error(f"手动登录失败: {e}")
            return False
            
    async def ensure_login(self, username: str = None, password: str = None) -> bool:
        """确保登录状态"""
        # 首先尝试使用cookies登录
        if await self.login_with_cookies():
            return True
            
        # 如果cookies登录失败，尝试手动登录
        logger.info("尝试手动登录...")
        if await self.manual_login(username, password):
            return True
            
        logger.error("无法建立登录状态")
        return False
        
    async def refresh_cookies(self) -> bool:
        """刷新cookies"""
        try:
            # 访问微博首页
            await self.scraper.page.goto("https://weibo.com")
            await self.scraper.page.wait_for_load_state("networkidle")
            
            # 检查登录状态
            if await self.scraper.check_login_status():
                # 获取并保存最新cookies
                cookies = await self.scraper.get_cookies()
                self.cookie_manager.save_cookies(cookies)
                logger.info("Cookies刷新成功")
                return True
            else:
                logger.warning("当前未登录，无法刷新cookies")
                return False
                
        except Exception as e:
            logger.error(f"刷新cookies失败: {e}")
            return False
            
    def get_login_suggestions(self) -> List[str]:
        """获取登录建议"""
        suggestions = []
        
        if not self.cookie_manager.has_cookies():
            suggestions.append("建议先手动登录一次以保存cookies")
            
        suggestions.extend([
            "使用真实浏览器进行登录以避免检测",
            "避免频繁登录操作",
            "定期刷新cookies保持登录状态",
            "使用代理IP以避免IP限制"
        ])
        
        return suggestions