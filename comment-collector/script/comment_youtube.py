#!/usr/bin/env python3
"""
YouTube Comment Collector - 专门用于爬取 YouTube Shorts 评论
支持：
  - 单个视频评论爬取
  - 批量视频评论爬取（自动导航）
  - 回复提取
  - 视频统计信息提取（点赞、评论数、分享数等）
"""

import argparse
import time
import re
import json
import atexit
import gc
from datetime import datetime
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from base_collector import BaseCollector


class YoutubeCollector(BaseCollector):
    """YouTube 评论收集器"""

    def __init__(self, headless: bool = True, timeout: int = 60):
        """初始化 YouTube 收集器

        Args:
            headless: 是否使用无头浏览器
            timeout: 页面加载超时时间（默认60秒）
        """
        super().__init__(headless, timeout)
        self.video_url = None
        self.video_stats = {
            "likes": 0,
            "dislikes": 0,
            "comments": 0,
            "shares": 0
        }
        self.videos_data = []

    def _get_platform_name(self) -> str:
        """获取平台名称"""
        return "youtube"

    def _get_comment_selector(self) -> str:
        """获取 YouTube 评论选择器"""
        return "#content-text, [data-testid='comment']"

    def _parse_count(self, text: str) -> int:
        """解析文本中的数字，处理中文单位（万）

        Args:
            text: 文本字符串，可能包含 "1.3万" 这样的格式

        Returns:
            解析后的数字
        """
        if not text:
            return 0

        text = text.strip()

        # 处理中文单位 "万" (10000)
        if "万" in text:
            match = re.search(r'(\d+(?:\.\d+)?)', text)
            if match:
                num = float(match.group(1))
                return int(num * 10000)
            return 0

        # 处理中文单位 "千" (1000)
        if "千" in text:
            match = re.search(r'(\d+(?:\.\d+)?)', text)
            if match:
                num = float(match.group(1))
                return int(num * 1000)
            return 0

        # 提取数字
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())

        return 0

    def _extract_video_stats(self):
        """提取视频统计信息（点赞数、评论数、分享数等）"""
        self._extract_video_stats_from_driver(self.driver)

    def _extract_video_stats_from_driver(self, driver):
        """从指定driver中提取视频统计信息（点赞数、评论数、分享数等）"""
        print("[INFO] 提取视频统计信息...")

        try:
            # 记录视频 URL
            self.video_url = driver.current_url
            print(f"[INFO] 视频 URL: {self.video_url}")

            # 在 #button-bar 中查找各个按钮
            try:
                # Button 0: 点赞数
                like_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "#button-bar reel-action-bar-view-model button-view-model:nth-child(1)"
                )
                like_text = (like_btn.get_attribute("textContent") or like_btn.text or "").strip()
                self.video_stats["likes"] = self._parse_count(like_text)
                print(f"[INFO] 点赞数: {like_text} ({self.video_stats['likes']})")
            except Exception as e:
                print(f"[WARN] 提取点赞数失败: {e}")

            try:
                # Button 1: 不喜欢（通常没有数字）
                dislike_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "#button-bar reel-action-bar-view-model button-view-model:nth-child(2)"
                )
                dislike_text = (dislike_btn.get_attribute("textContent") or dislike_btn.text or "").strip()
                self.video_stats["dislikes"] = self._parse_count(dislike_text)
                print(f"[INFO] 不喜欢: {dislike_text} ({self.video_stats['dislikes']})")
            except Exception as e:
                print(f"[WARN] 提取不喜欢数失败: {e}")

            try:
                # Button 2: 评论数
                comment_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "#button-bar reel-action-bar-view-model button-view-model:nth-child(3)"
                )
                comment_text = (comment_btn.get_attribute("textContent") or comment_btn.text or "").strip()
                self.video_stats["comments"] = self._parse_count(comment_text)
                print(f"[INFO] 评论数: {comment_text} ({self.video_stats['comments']})")
            except Exception as e:
                print(f"[WARN] 提取评论数失败: {e}")

            try:
                # Button 3: 分享数
                share_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "#button-bar reel-action-bar-view-model button-view-model:nth-child(4)"
                )
                share_text = (share_btn.get_attribute("textContent") or share_btn.text or "").strip()
                self.video_stats["shares"] = self._parse_count(share_text)
                print(f"[INFO] 分享数: {share_text} ({self.video_stats['shares']})")
            except Exception as e:
                print(f"[WARN] 提取分享数失败: {e}")

        except Exception as e:
            print(f"[WARN] 提取视频统计信息失败: {e}")

    def _wait_for_comments(self):
        """等待 YouTube 评论加载完成"""
        self._wait_for_comments_from_driver(self.driver)

    def _wait_for_comments_from_driver(self, driver):
        """等待 YouTube 评论加载完成"""
        print("[INFO] 等待 YouTube 评论加载...")

        # 初始等待让页面完全加载
        time.sleep(2)

        # 对于 YouTube Shorts，需要点击评论按钮
        click_success = False
        for attempt in range(3):
            try:
                print(f"[INFO] 尝试点击评论按钮 (尝试 {attempt+1}/3)...")
                driver.execute_script("""
                    var btn = document.querySelector('#button-bar > reel-action-bar-view-model > button-view-model:nth-child(3) > label > button > yt-touch-feedback-shape > div.yt-spec-touch-feedback-shape__fill');
                    if (btn) {
                        btn.click();
                        console.log('评论按钮已点击');
                    } else {
                        console.log('未找到评论按钮');
                    }
                """)
                click_success = True
                time.sleep(3)
                break
            except Exception as e:
                print(f"[WARN] 点击评论按钮失败 (尝试 {attempt+1}): {e}")
                time.sleep(1)

        if not click_success:
            print(f"[WARN] 无法点击评论按钮，尝试等待可能的自动加载...")

        # 等待评论容器出现
        max_wait = 40
        for i in range(max_wait):
            comment_count = self._count_loaded_comments_from_driver(driver)
            print(f"[INFO] 等待评论加载... 已找到 {comment_count} 条 ({i+1}/{max_wait})")

            if comment_count >= 1:
                print(f"[INFO] 评论已加载")
                return True

            time.sleep(0.5)

        print(f"[WARN] 等待超时，评论未加载")
        return False

    def _scroll_to_load(self, scroll_times: int = 5, delay: float = 2.0, target_comments: int = 100):
        """YouTube 特定的增量滚动策略 - 在评论容器内滚动"""
        self._scroll_to_load_from_driver(self.driver, scroll_times, delay, target_comments)

    def _scroll_to_load_from_driver(self, driver, scroll_times: int = 5, delay: float = 2.0, target_comments: int = 100):
        """YouTube 特定的增量滚动策略 - 在评论容器内滚动

        Args:
            driver: WebDriver实例
            scroll_times: 滚动次数
            delay: 每次滚动间的延迟
            target_comments: 目标评论数
        """
        print(f"[INFO] 开始增量滚动加载评论，目标 {target_comments} 条...")

        # 定位到评论容器 #contents
        comment_container = None
        try:
            comment_container = driver.find_element(By.CSS_SELECTOR, "#contents")
            print("[INFO] 找到评论容器 #contents")
        except:
            print("[WARN] 未找到 #contents，尝试使用页面滚动")

        no_change_count = 0
        total_scrolls = 0
        max_scrolls = scroll_times * 10
        last_count = 0

        while total_scrolls < max_scrolls:
            total_scrolls += 1

            # 获取当前评论数
            current_count = self._count_loaded_comments_from_driver(driver)
            print(f"[INFO] 当前已加载评论: {current_count} 条 (滚动 {total_scrolls}/{max_scrolls})")

            if current_count >= target_comments:
                print(f"[INFO] 已达到目标评论数 {target_comments}")
                break

            # 滚动评论容器
            if comment_container:
                try:
                    # 在 #contents 容器内滚动到底部
                    driver.execute_script(
                        """
                        arguments[0].scrollTop = arguments[0].scrollTop + 300;
                        """,
                        comment_container
                    )
                except Exception as e:
                    print(f"[WARN] 容器滚动失败: {e}，尝试页面滚动")
                    driver.execute_script(f"window.scrollBy(0, 300);")
            else:
                # 页面滚动
                driver.execute_script(f"window.scrollBy(0, 300);")

            time.sleep(delay)

            # 检查评论数是否增加
            new_count = self._count_loaded_comments_from_driver(driver)

            # 尝试点击"加载更多"按钮（如果有）
            clicked = self._click_load_more_from_driver(driver)

            if new_count == last_count and not clicked:
                no_change_count += 1
                print(f"[INFO] 评论数量未变化 ({no_change_count}/5)")
                if no_change_count >= 5:
                    print(f"[INFO] 评论加载完成（连续5次无新评论）")
                    break
            else:
                no_change_count = 0

            last_count = new_count
            time.sleep(0.3)

        print(f"[INFO] 滚动结束，共滚动 {total_scrolls} 次，加载评论 {last_count} 条")

    def _count_loaded_comments_from_driver(self, driver) -> int:
        """获取当前加载的评论数量"""
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, "ytd-comment-thread-renderer")
            return len(elements)
        except:
            return 0

    def _click_load_more_from_driver(self, driver) -> bool:
        """尝试点击'加载更多'按钮"""
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Load more']")
            for btn in buttons:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    return True
        except:
            pass
        return False

    def _get_comment_elements(self) -> List:
        """获取 YouTube 评论元素列表 - 使用更精确的去重"""
        return self._get_comment_elements_from_driver(self.driver)

    def _get_comment_elements_from_driver(self, driver) -> List:
        """获取 YouTube 评论元素列表"""
        print("[INFO] 开始查找评论元素...")

        selector = "ytd-comment-thread-renderer"

        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"[INFO] 找到 {len(elements)} 个评论元素")

            all_elements = []
            seen_authors = {}

            for elem in elements:
                try:
                    # 尝试提取作者名和内容作为唯一标识
                    author = ""
                    try:
                        author_elem = elem.find_element(By.CSS_SELECTOR, "#author-text")
                        author = (author_elem.get_attribute("textContent") or author_elem.text or "").strip()
                    except:
                        pass

                    content = ""
                    try:
                        content_elem = elem.find_element(By.CSS_SELECTOR, "#content-text")
                        content = (content_elem.get_attribute("textContent") or content_elem.text or "").strip()[:100]
                    except:
                        pass

                    # 使用 (作者 + 内容) 作为唯一标识
                    unique_key = f"{author}||{content}"

                    if unique_key not in seen_authors and content:
                        seen_authors[unique_key] = True
                        all_elements.append(elem)
                    elif not unique_key:
                        all_elements.append(elem)

                except Exception as e:
                    try:
                        all_elements.append(elem)
                    except:
                        pass

            print(f"[INFO] 去重后共 {len(all_elements)} 个评论元素")
            return all_elements

        except Exception as e:
            print(f"[WARN] 查找评论元素失败: {e}")
            return []

    def _extract_comment(self, element) -> Optional[Dict]:
        """从元素中提取 YouTube 评论"""
        try:
            # 提取作者名
            author = ""
            for selector in [
                "#author-text",
                "a[href^='/@']",
                "a[href^='/']",
                "#author-name",
                "[data-testid='comment-author-name']",
                "a.yt-user-name",
                ".yt-user-name",
                "[href*='/channel/']",
            ]:
                try:
                    author_elem = element.find_element(By.CSS_SELECTOR, selector)
                    author = (author_elem.get_attribute("textContent") or author_elem.text or "").strip()
                    if author:
                        break
                except NoSuchElementException:
                    continue

            # 提取评论内容
            content = ""
            for selector in [
                "#content-text",
                "[data-testid='comment-text']",
                ".comment-text",
                "yt-formatted-string.content",
            ]:
                try:
                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                    content = (content_elem.get_attribute("textContent") or content_elem.text or "").strip()
                    if content:
                        break
                except NoSuchElementException:
                    continue

            # 提取发布时间
            time_str = ""
            for selector in [
                "yt-formatted-string.published-time-label",
                "[aria-label*='ago']",
                ".published-time-label",
                "span.relative-time",
            ]:
                try:
                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                    time_str = (time_elem.get_attribute("aria-label") or
                               time_elem.get_attribute("textContent") or
                               time_elem.text or "").strip()
                    if time_str:
                        break
                except NoSuchElementException:
                    continue

            # 提取点赞数
            likes = 0
            for selector in [
                "#vote-count-up",
                "[aria-label*='like']",
                ".yt-core-attributed-string.comment-action-buttons",
            ]:
                try:
                    like_elem = element.find_element(By.CSS_SELECTOR, selector)
                    like_text = like_elem.get_attribute("textContent") or like_elem.text or ""
                    numbers = ''.join(filter(str.isdigit, like_text))
                    if numbers:
                        likes = int(numbers)
                        break
                except (NoSuchElementException, ValueError):
                    continue

            # 如果内容为空，跳过
            if not content or len(content.strip()) < 3:
                return None

            return {
                "author": author,
                "content": content,
                "time": time_str,
                "likes": likes
            }
        except Exception as e:
            print(f"[WARN] 提取 YouTube 评论失败: {e}")
            return None

    def _extract_comment_replies(self, comment_element, max_replies: int = 100) -> List[Dict]:
        """提取 YouTube 评论的回复"""
        replies = []

        try:
            # 尝试找到并点击"显示回复"按钮
            show_replies_selectors = [
                "[aria-label*='Show replies']",
                "[aria-label*='show reply']",
                "yt-button-shape[aria-label*='replies']",
                ".comment-replies-button",
            ]

            for selector in show_replies_selectors:
                try:
                    buttons = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            try:
                                btn.click()
                                print("[INFO] 点击显示回复")
                                time.sleep(2)
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(2)
                except:
                    continue

            # 在评论元素中查找回复
            reply_selectors = [
                "ytd-comment-replies-renderer",
                "#reply-container",
                ".comment-replies",
            ]

            reply_elements = []
            for selector in reply_selectors:
                try:
                    elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        reply_elements.extend(elements)
                        print(f"[INFO] 找到 {len(elements)} 个回复容器")
                        break
                except:
                    continue

            # 提取回复内容
            for idx, reply_elem in enumerate(reply_elements[:max_replies]):
                try:
                    reply = self._extract_single_reply(reply_elem)
                    if reply and reply.get("content"):
                        reply["index"] = idx + 1
                        replies.append(reply)
                except:
                    continue

            print(f"[INFO] 成功提取 {len(replies)} 条回复")
            return replies

        except Exception as e:
            print(f"[WARN] 提取回复失败: {e}")
            return replies

    def _extract_single_reply(self, reply_element) -> Optional[Dict]:
        """提取单条回复"""
        try:
            # 提取回复作者
            author = ""
            for selector in [
                "#author-text",
                "a[href^='/@']",
                "a[href^='/']",
                "#author-name",
                "[data-testid='comment-author-name']",
                "a.yt-user-name",
            ]:
                try:
                    author_elem = reply_element.find_element(By.CSS_SELECTOR, selector)
                    author = (author_elem.get_attribute("textContent") or author_elem.text or "").strip()
                    if author:
                        break
                except:
                    continue

            # 提取回复内容
            content = ""
            for selector in [
                "#content-text",
                "[data-testid='comment-text']",
                "yt-formatted-string.content",
            ]:
                try:
                    content_elem = reply_element.find_element(By.CSS_SELECTOR, selector)
                    content = (content_elem.get_attribute("textContent") or content_elem.text or "").strip()
                    if content:
                        break
                except:
                    continue

            if not content or len(content.strip()) < 2:
                return None

            return {
                "author": author,
                "content": content,
                "time": "",
                "likes": 0
            }
        except Exception as e:
            print(f"[WARN] 提取回复失败: {e}")
            return None

    def save(self, output_path: str = "comments.json"):
        """保存评论和视频信息到 JSON 文件

        Args:
            output_path: 输出文件路径
        """
        if not self.comments:
            print("[WARN] 没有评论需要保存")
            return

        output_data = {
            "metadata": {
                "url": self.video_url,
                "collected_at": datetime.now().isoformat(),
                "total_count": len(self.comments),
                "platform": self._get_platform_name(),
                "video_stats": {
                    "likes": self.video_stats["likes"],
                    "dislikes": self.video_stats["dislikes"],
                    "comments": self.video_stats["comments"],
                    "shares": self.video_stats["shares"]
                }
            },
            "comments": self.comments
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 评论已保存到: {output_path}")
        except Exception as e:
            print(f"[ERROR] 保存文件失败: {e}")

    def _navigate_to_next_video(self, driver=None, retry_count: int = 3) -> bool:
        """使用键盘向下键导航到下一个视频

        Args:
            driver: WebDriver实例（如果为None则使用self.driver）
            retry_count: 重试次数

        Returns:
            是否成功导航到下一个视频
        """
        if driver is None:
            driver = self.driver

        print("[INFO] 导航到下一个视频...")

        for attempt in range(retry_count):
            try:
                # 关闭评论面板（Escape键）
                try:
                    actions = ActionChains(driver)
                    actions.send_keys(Keys.ESCAPE).perform()
                    print("[INFO] 已按Escape关闭评论面板")
                    time.sleep(1)
                except:
                    pass

                # 直接在页面上按下向下键
                actions = ActionChains(driver)
                actions.send_keys(Keys.ARROW_DOWN).perform()

                print(f"[INFO] 已按下向下键（尝试 {attempt + 1}/{retry_count}）")
                time.sleep(4)  # 增加等待时间让页面加载

                # 检查 URL 是否改变
                current_url = driver.current_url
                print(f"[INFO] 当前 URL: {current_url}")

                if "shorts/" in current_url:
                    # 刷新页面以重置YouTube应用状态（确保评论面板正确初始化）
                    print("[INFO] 刷新页面以重置YouTube应用状态...")
                    driver.refresh()
                    time.sleep(3)
                    return True

            except Exception as e:
                print(f"[WARN] 导航失败（尝试 {attempt + 1}）: {e}")
                time.sleep(1)

        return False

    def collect_batch(self, video_count: int = 5, output_file: str = "youtube_shorts_batch.json"):
        """批量爬取多个视频的评论

        Args:
            video_count: 要爬取的视频数量
            output_file: 输出文件路径
        """
        print(f"\n{'='*70}")
        print(f"YouTube Shorts 批量评论爬虫")
        print(f"{'='*70}")
        print(f"目标: 爬取 {video_count} 个视频的评论\n")

        driver = None
        try:
            # 初始化浏览器
            driver = self._init_driver()

            # 访问 YouTube Shorts 首页
            print("[INFO] 访问 YouTube Shorts 首页...")
            driver.get("https://www.youtube.com/shorts")
            time.sleep(3)

            # 爬取多个视频
            for i in range(video_count):
                print(f"\n[PROGRESS] 进度: {i+1}/{video_count}")

                # 获取当前视频 URL
                video_url = driver.current_url

                if "shorts/" not in video_url:
                    print("[WARN] 未在 Shorts 页面，跳过此视频")
                else:
                    # 爬取视频评论（复用主driver）
                    video_data = self._collect_single_video_in_batch(driver, video_url, i + 1)

                    if video_data:
                        self.videos_data.append(video_data)
                        print(f"[SUCCESS] 视频 {i+1} 爬取完成")
                    else:
                        print(f"[WARN] 视频 {i+1} 爬取失败，继续下一个")

                # 如果不是最后一个视频，导航到下一个
                if i < video_count - 1:
                    print(f"\n[INFO] 导航到下一个视频...")
                    time.sleep(1)

                    if not self._navigate_to_next_video(driver):
                        print(f"[WARN] 无法导航到下一个视频，停止爬取")
                        break

            # 保存结果
            self._save_batch_data(output_file)

            print(f"\n{'='*70}")
            print(f"[SUCCESS] 批量爬取完成！")
            print(f"[INFO] 共爬取 {len(self.videos_data)} 个视频")
            print(f"[INFO] 结果已保存到: {output_file}")
            print(f"{'='*70}")

        except Exception as e:
            print(f"[ERROR] 批量爬取失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 确保浏览器被正确关闭
            if driver is not None:
                try:
                    driver.quit()
                    print("[INFO] 浏览器已关闭")
                except Exception as e:
                    print(f"[WARN] 关闭浏览器失败: {e}")

            # 强制垃圾回收
            gc.collect()

    def _collect_single_video_in_batch(self, driver, video_url: str, index: int) -> dict:
        """在批量模式中爬取单个视频的评论（复用主driver）

        Args:
            driver: 已初始化的WebDriver实例
            video_url: 视频 URL
            index: 视频索引

        Returns:
            视频数据字典
        """
        print(f"\n{'='*70}")
        print(f"[VIDEO {index}] 正在爬取视频评论...")
        print(f"{'='*70}")
        print(f"URL: {video_url}\n")

        try:
            # 提取视频统计信息
            self._extract_video_stats_from_driver(driver)

            # 等待评论加载
            self._wait_for_comments_from_driver(driver)

            # 滚动加载评论
            self._scroll_to_load_from_driver(driver, scroll_times=10, delay=1.0, target_comments=100)

            # 获取评论元素
            comment_elements = self._get_comment_elements_from_driver(driver)
            print(f"[INFO] 找到 {len(comment_elements)} 个评论元素")

            # 提取评论
            comments = []
            for idx, elem in enumerate(comment_elements[:100]):
                try:
                    comment = self._extract_comment(elem)
                    if comment:
                        comment["index"] = idx + 1
                        comments.append(comment)
                except Exception as e:
                    print(f"[WARN] 提取第 {idx + 1} 条评论失败: {e}")

            print(f"[INFO] 成功提取 {len(comments)} 条评论")

            video_data = {
                "index": index,
                "url": video_url,
                "collected_at": datetime.now().isoformat(),
                "video_stats": {
                    "likes": self.video_stats["likes"],
                    "dislikes": self.video_stats["dislikes"],
                    "comments": self.video_stats["comments"],
                    "shares": self.video_stats["shares"]
                },
                "total_comments_collected": len(comments),
                "comments": comments
            }

            return video_data

        except Exception as e:
            print(f"[ERROR] 爬取视频 {index} 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _collect_single_video(self, video_url: str, index: int) -> dict:
        """爬取单个视频的评论（单视频模式）

        Args:
            video_url: 视频 URL
            index: 视频索引

        Returns:
            视频数据字典
        """
        print(f"\n{'='*70}")
        print(f"[VIDEO {index}] 正在爬取视频评论...")
        print(f"{'='*70}")
        print(f"URL: {video_url}\n")

        driver = None
        try:
            # 创建驱动
            driver = self._init_driver()

            # 访问视频页面
            driver.get(video_url)
            time.sleep(3)

            # 提取视频统计信息
            self._extract_video_stats_from_driver(driver)

            # 等待评论加载
            self._wait_for_comments_from_driver(driver)

            # 滚动加载评论
            self._scroll_to_load_from_driver(driver, scroll_times=10, delay=1.0, target_comments=100)

            # 获取评论元素
            comment_elements = self._get_comment_elements_from_driver(driver)
            print(f"[INFO] 找到 {len(comment_elements)} 个评论元素")

            # 提取评论
            comments = []
            for idx, elem in enumerate(comment_elements[:100]):
                try:
                    comment = self._extract_comment(elem)
                    if comment:
                        comment["index"] = idx + 1
                        comments.append(comment)
                except Exception as e:
                    print(f"[WARN] 提取第 {idx + 1} 条评论失败: {e}")

            print(f"[INFO] 成功提取 {len(comments)} 条评论")

            video_data = {
                "index": index,
                "url": video_url,
                "collected_at": datetime.now().isoformat(),
                "video_stats": {
                    "likes": self.video_stats["likes"],
                    "dislikes": self.video_stats["dislikes"],
                    "comments": self.video_stats["comments"],
                    "shares": self.video_stats["shares"]
                },
                "total_comments_collected": len(comments),
                "comments": comments
            }

            return video_data

        except Exception as e:
            print(f"[ERROR] 爬取视频 {index} 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            # 确保驱动被正确关闭
            if driver is not None:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"[WARN] 关闭驱动失败: {e}")

    def _save_batch_data(self, output_file: str):
        """保存批量爬取的数据到 JSON 文件

        Args:
            output_file: 输出文件路径
        """
        output_data = {
            "metadata": {
                "collected_at": datetime.now().isoformat(),
                "total_videos": len(self.videos_data),
                "platform": "youtube_shorts",
                "total_comments": sum(v["total_comments_collected"] for v in self.videos_data)
            },
            "videos": self.videos_data
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 数据已保存到: {output_file}")
        except Exception as e:
            print(f"[ERROR] 保存文件失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Comment Collector - 爬取 YouTube Shorts 评论",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 爬取单个视频
  %(prog)s --url "https://www.youtube.com/shorts/abc123"

  # 爬取 5 个视频（从 Shorts 首页自动导航）
  %(prog)s --batch --count 5

  # 提取评论回复
  %(prog)s --url "https://www.youtube.com/shorts/abc123" --ensure_fedback
        """
    )

    parser.add_argument(
        "--url", "-u",
        help="YouTube Shorts 视频 URL（单个视频模式）"
    )

    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量模式：从 Shorts 首页自动导航爬取多个视频"
    )

    parser.add_argument(
        "--count", "-c",
        type=int,
        default=5,
        help="批量模式下要爬取的视频数量（默认：5）"
    )

    parser.add_argument(
        "--output", "-o",
        default="comments.json",
        help="输出文件路径（默认：comments.json）"
    )

    parser.add_argument(
        "--max_comments", "-m",
        type=int,
        default=100,
        help="最大爬取评论数（默认：100）"
    )

    parser.add_argument(
        "--scroll_times", "-s",
        type=int,
        default=5,
        help="滚动次数（默认：5）"
    )

    parser.add_argument(
        "--ensure_fedback",
        action="store_true",
        help="提取评论下的回复"
    )

    parser.add_argument(
        "--max_replies",
        type=int,
        default=100,
        help="每条评论的最大回复数（默认：100）"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头浏览器（默认启用）"
    )

    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="禁用无头浏览器，显示浏览器窗口"
    )

    args = parser.parse_args()

    # 检查参数
    if not args.url and not args.batch:
        parser.print_help()
        print("\n[ERROR] 请指定 --url（单个视频）或 --batch（批量模式）")
        return

    try:
        if args.batch:
            # 批量模式
            collector = YoutubeCollector(headless=args.headless)
            collector.collect_batch(video_count=args.count, output_file=args.output)
        else:
            # 单个视频模式
            with YoutubeCollector(headless=args.headless) as collector:
                comments = collector.collect(
                    url=args.url,
                    max_comments=args.max_comments,
                    scroll_times=args.scroll_times,
                    ensure_fedback=args.ensure_fedback,
                    max_replies=args.max_replies
                )

                # 保存评论
                if comments:
                    collector.save(args.output)
                    print(f"\n[SUCCESS] 成功爬取 {len(comments)} 条评论")
                else:
                    print("\n[ERROR] 未爬取到任何评论")

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断爬取")
    except Exception as e:
        print(f"\n[ERROR] 爬取失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
