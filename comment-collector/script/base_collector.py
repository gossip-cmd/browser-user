#!/usr/bin/env python3
"""
Base Comment Collector - 统一的爬虫基类
所有平台特定的爬虫都应继承此类
"""

import json
import time
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class BaseCollector(ABC):
    """评论收集器基类 - 定义通用的爬虫框架和工具方法"""

    # 常见评论区选择器映射（平台特定爬虫可覆盖）
    COMMON_SELECTORS = {
        "youtube": "ytd-comment-thread-renderer #content-text",
        "reddit": "[data-testid='comment']",
        "twitter": "[data-testid='tweetText']",
        "weibo": ".list_con .txt",
        "zhihu": ".CommentItemV2-content",
        "bilibili": ".reply-wrap",
        "xiaohongshu": ".comment-item, .feed-item",
        "tiktok": "[data-testid='comment']",
        "douyin": ".comment-item",
        "default": ".comment, .comments, [class*='comment'], [class*='Comment']"
    }

    def __init__(self, headless: bool = True, timeout: int = 30):
        """初始化爬虫

        Args:
            headless: 是否使用无头浏览器
            timeout: 页面加载超时时间（秒）
        """
        self.headless = headless
        self.timeout = timeout
        self.driver: Optional[webdriver.Chrome] = None
        self.comments: List[Dict] = []

    def _init_driver(self) -> webdriver.Chrome:
        """初始化 Chrome WebDriver

        Returns:
            WebDriver 实例
        """
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        # 禁用图片加载以提高性能
        chrome_options.add_experimental_option(
            "prefs", {"profile.managed_default_content_settings.images": 2}
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(self.timeout)

        return driver

    def _add_cookies(self, url: str, cookie_str: Optional[str] = None):
        """添加 Cookie 到浏览器

        Args:
            url: 目标 URL
            cookie_str: Cookie 字符串（格式：key1=value1;key2=value2）
        """
        if not cookie_str:
            return

        print("[INFO] 正在添加 Cookie...")

        # 解析 cookie 字符串
        cookies = {}
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value

        # 先访问域名主页
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        self.driver.get(domain)
        time.sleep(2)

        # 添加 cookies
        for name, value in cookies.items():
            try:
                self.driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': parsed.netloc.replace('www.', '.'),
                    'path': '/'
                })
            except Exception as e:
                print(f"[WARN] 添加 cookie {name} 失败: {e}")

        print(f"[INFO] 已添加 {len(cookies)} 个 Cookie")

    def _add_cookies_from_file(self, url: str, cookie_file: str):
        """从文件中加载 Cookie

        Args:
            url: 目标 URL
            cookie_file: Cookie 文件路径
        """
        if not os.path.exists(cookie_file):
            print(f"[WARN] Cookie 文件不存在: {cookie_file}")
            return

        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_str = f.read().strip()
            self._add_cookies(url, cookie_str)
        except Exception as e:
            print(f"[WARN] 读取 Cookie 文件失败: {e}")

    def _scroll_to_load(self, scroll_times: int = 5, delay: float = 2.0, target_comments: int = 100):
        """滚动页面加载更多评论，使用小增量滚动

        Args:
            scroll_times: 滚动次数
            delay: 每次滚动间的延迟（秒）
            target_comments: 目标评论数
        """
        print(f"[INFO] 开始滚动页面，目标加载 {target_comments} 条评论...")

        # 获取当前滚动位置
        current_scroll = self.driver.execute_script("return window.scrollY;")
        no_change_count = 0
        total_scrolls = 0
        max_scrolls = scroll_times * 3  # 增加最大滚动次数
        last_count = 0

        while total_scrolls < max_scrolls:
            total_scrolls += 1

            # 获取当前评论数
            current_count = self._count_loaded_comments()
            print(f"[INFO] 当前已加载评论: {current_count} 条 (滚动 {total_scrolls}/{max_scrolls})")

            if current_count >= target_comments:
                print(f"[INFO] 已达到目标评论数 {target_comments}")
                break

            # 使用小增量滚动，而不是直接滚动到底部
            current_scroll += 800  # 每次滚动800像素
            self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
            time.sleep(delay)

            # 检查评论数是否增加
            new_count = self._count_loaded_comments()

            # 尝试点击"加载更多"按钮（如果有）
            clicked = self._click_load_more()

            if new_count == last_count and not clicked:
                no_change_count += 1
                if no_change_count >= 3:
                    print(f"[INFO] 评论数量连续 {no_change_count} 次未变化，停止滚动")
                    break
            else:
                no_change_count = 0

            last_count = new_count

            # 额外等待让评论加载
            time.sleep(0.5)

        print(f"[INFO] 滚动结束，共滚动 {total_scrolls} 次")

    def _count_loaded_comments(self) -> int:
        """统计当前页面已加载的评论数量（可被子类覆盖）

        Returns:
            评论数量
        """
        try:
            # 获取平台特定的选择器
            selector = self._get_comment_selector()
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

            seen_ids = set()
            for elem in elements:
                data_id = elem.get_attribute("data-id")
                if data_id:
                    seen_ids.add(data_id)
                else:
                    # 如果没有 data-id，则计数所有元素
                    seen_ids.add(str(id(elem)))

            return len(seen_ids) if seen_ids else len(elements)
        except Exception:
            return 0

    def _click_load_more(self) -> bool:
        """尝试点击加载更多按钮

        Returns:
            是否点击成功
        """
        load_more_selectors = [
            ".reply-box .view-more",
            ".reply-more",
            ".load-more",
            ".view-more",
            ".fetch-more",
            ".bottom-more",
            ".pagination-next",
            "[class*='load-more']",
            "[class*='view-more']",
            "[class*='fetch-more']",
        ]

        clicked = False
        for selector in load_more_selectors:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        text = btn.text or btn.get_attribute("textContent") or ""
                        # 使用 nearest 滚动，避免滚动过多
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});",
                            btn
                        )
                        time.sleep(0.3)
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        print(f"[INFO] 点击加载更多按钮: {text[:40]}... ({selector})")
                        time.sleep(1.5)  # 等待加载
                        clicked = True
            except Exception:
                continue
        return clicked

    def _safe_extract(self, element, selector: str) -> str:
        """安全地从元素中提取文本

        Args:
            element: WebElement
            selector: CSS 选择器

        Returns:
            提取的文本，失败返回空字符串
        """
        try:
            elem = element.find_element(By.CSS_SELECTOR, selector)
            return (elem.get_attribute("textContent") or elem.text or "").strip()
        except NoSuchElementException:
            return ""

    def _safe_extract_text(self, element) -> str:
        """安全地提取元素的所有文本

        Args:
            element: WebElement

        Returns:
            元素的文本内容
        """
        try:
            text = element.get_attribute("textContent") or element.text or ""
            return text.strip()
        except Exception:
            return ""

    def _safe_extract_number(self, element, selector: str) -> int:
        """安全地从元素中提取数字

        Args:
            element: WebElement
            selector: CSS 选择器

        Returns:
            提取的数字，失败返回 0
        """
        try:
            elem = element.find_element(By.CSS_SELECTOR, selector)
            text = elem.get_attribute("textContent") or elem.text or ""
            numbers = ''.join(filter(str.isdigit, text))
            return int(numbers) if numbers else 0
        except (NoSuchElementException, ValueError):
            return 0

    @abstractmethod
    def _wait_for_comments(self):
        """等待评论加载完成（平台特定）"""
        pass

    @abstractmethod
    def _get_comment_elements(self) -> List:
        """获取评论元素列表（平台特定）

        Returns:
            WebElement 列表
        """
        pass

    @abstractmethod
    def _get_comment_selector(self) -> str:
        """获取评论选择器（平台特定）

        Returns:
            CSS 选择器
        """
        pass

    @abstractmethod
    def _extract_comment(self, element) -> Optional[Dict]:
        """从元素中提取评论信息（平台特定）

        Args:
            element: WebElement

        Returns:
            评论字典或 None
        """
        pass

    def _extract_comment_replies(self, comment_element, max_replies: int = 100) -> List[Dict]:
        """提取评论下的回复（可选实现，子类覆盖）

        Args:
            comment_element: WebElement
            max_replies: 最大回复数

        Returns:
            回复列表
        """
        return []

    def collect(self, url: str, selector: Optional[str] = None,
                max_comments: int = 100, scroll_times: int = 5,
                ensure_fedback: bool = False, max_replies: int = 100,
                **kwargs) -> List[Dict]:
        """主要的评论收集方法

        Args:
            url: 目标 URL
            selector: 自定义 CSS 选择器
            max_comments: 最大评论数
            scroll_times: 滚动次数
            ensure_fedback: 是否提取回复
            max_replies: 最大回复数
            **kwargs: 其他平台特定参数

        Returns:
            评论列表
        """
        try:
            self.driver = self._init_driver()

            # 加载 Cookie（如果有）
            if 'cookies' in kwargs and kwargs['cookies']:
                self._add_cookies(url, kwargs['cookies'])
            elif 'cookies_file' in kwargs and kwargs['cookies_file']:
                self._add_cookies_from_file(url, kwargs['cookies_file'])

            # 访问页面
            print(f"[INFO] 正在打开页面: {url}")
            self.driver.get(url)
            time.sleep(3)

            # 等待评论加载
            print("[INFO] 等待评论加载...")
            self._wait_for_comments()

            # 滚动加载更多评论
            self._scroll_to_load(scroll_times, 2.0, max_comments)

            # 获取评论元素
            comment_elements = self._get_comment_elements()
            print(f"[INFO] 找到 {len(comment_elements)} 个评论元素")

            # 提取评论
            for idx, elem in enumerate(comment_elements[:max_comments]):
                try:
                    comment = self._extract_comment(elem)
                    if comment:
                        comment["index"] = idx + 1

                        # 如果需要，提取回复
                        if ensure_fedback:
                            replies = self._extract_comment_replies(elem, max_replies)
                            if replies:
                                comment["replies"] = replies

                        self.comments.append(comment)
                except Exception as e:
                    print(f"[WARN] 提取第 {idx + 1} 条评论失败: {e}")

            print(f"[INFO] 成功提取 {len(self.comments)} 条评论")
            return self.comments

        except Exception as e:
            print(f"[ERROR] 爬取失败: {e}")
            return []

    def save(self, output_path: str = "comments.json"):
        """保存评论到 JSON 文件

        Args:
            output_path: 输出文件路径
        """
        if not self.comments:
            print("[WARN] 没有评论需要保存")
            return

        output_data = {
            "metadata": {
                "collected_at": datetime.now().isoformat(),
                "total_count": len(self.comments),
                "platform": self._get_platform_name()
            },
            "comments": self.comments
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 评论已保存到: {output_path}")
        except Exception as e:
            print(f"[ERROR] 保存文件失败: {e}")

    def _get_platform_name(self) -> str:
        """获取平台名称（子类应覆盖）

        Returns:
            平台名称
        """
        return "unknown"

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("[INFO] 浏览器已关闭")

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.close()
