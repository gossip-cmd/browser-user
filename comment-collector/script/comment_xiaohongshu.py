#!/usr/bin/env python3
"""
Xiaohongshu Comment Collector - 专门用于爬取小红书评论
支持：评论爬取、回复提取、Cookie 登录
"""

import argparse
import os
import time
from typing import List, Dict, Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from base_collector import BaseCollector


class XiaohongshuCollector(BaseCollector):
    """小红书评论收集器"""

    def _get_platform_name(self) -> str:
        """获取平台名称"""
        return "xiaohongshu"

    def _get_comment_selector(self) -> str:
        """获取小红书评论选择器"""
        return ".comment-item, .feed-item, [class*='comment']"

    def _wait_for_comments(self):
        """等待小红书评论加载完成"""
        print("[INFO] 等待小红书评论加载...")

        # 先滚动到页面底部触发评论区域加载
        for scroll_pos in [500, 1000, 1500, 2000]:
            self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
            time.sleep(1)

        # 等待评论容器出现
        max_wait = 30
        for i in range(max_wait):
            comment_count = self._count_loaded_comments()
            print(f"[INFO] 等待评论加载... 已找到 {comment_count} 条 ({i+1}/{max_wait})")

            if comment_count >= 3:
                print(f"[INFO] 评论已加载")
                break

            time.sleep(1)

    def _get_comment_elements(self) -> List:
        """获取小红书评论元素列表"""
        selectors = [
            ".comment-item",
            ".feed-item",
            "[class*='comment-list'] > div",
            ".comments-container [class*='comment']",
        ]

        all_elements = []
        seen_texts = set()

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"[INFO] 选择器 '{selector}' 找到 {len(elements)} 个元素")

                for elem in elements:
                    try:
                        # 获取评论文本内容用于去重
                        text = elem.text[:100] if elem.text else ""
                        if text and text not in seen_texts:
                            seen_texts.add(text)
                            all_elements.append(elem)
                    except:
                        all_elements.append(elem)

            except Exception as e:
                print(f"[WARN] 选择器 '{selector}' 失败: {e}")
                continue

        print(f"[INFO] 去重后共 {len(all_elements)} 个评论元素")
        return all_elements

    def _extract_comment(self, element) -> Optional[Dict]:
        """从元素中提取小红书评论"""
        try:
            # 提取用户名
            author = ""
            for selector in [
                ".user-name",
                ".author-name",
                "[class*='username']",
                "a[class*='user']",
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
                ".comment-text",
                ".content",
                "[class*='desc']",
                ".comment-content",
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
                ".comment-time",
                ".time",
                "[class*='time']",
            ]:
                try:
                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                    time_str = (time_elem.get_attribute("textContent") or time_elem.text or "").strip()
                    if time_str:
                        break
                except NoSuchElementException:
                    continue

            # 提取点赞数
            likes = 0
            for selector in [
                ".like-count",
                ".like-num",
                "[class*='like']",
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
            print(f"[WARN] 提取小红书评论失败: {e}")
            return None

    def _extract_comment_replies(self, comment_element, max_replies: int = 100) -> List[Dict]:
        """提取小红书评论的回复"""
        replies = []

        try:
            # 尝试找到并点击"查看回复"按钮
            show_replies_selectors = [
                ".view-replies",
                ".show-replies",
                "[class*='view-reply']",
                ".reply-toggle",
            ]

            for selector in show_replies_selectors:
                try:
                    buttons = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            try:
                                btn.click()
                                print("[INFO] 点击查看回复")
                                time.sleep(2)
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(2)
                except:
                    continue

            # 在评论元素中查找回复
            reply_selectors = [
                ".reply-item",
                ".sub-comment",
                "[class*='reply']",
            ]

            reply_elements = []
            for selector in reply_selectors:
                try:
                    elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        reply_elements.extend(elements)
                        print(f"[INFO] 找到 {len(elements)} 个回复")
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
                ".user-name",
                ".author-name",
                "[class*='username']",
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
                ".comment-text",
                ".content",
                ".reply-content",
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


def main():
    parser = argparse.ArgumentParser(
        description="Xiaohongshu Comment Collector - 爬取小红书评论",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  %(prog)s --url "https://www.xiaohongshu.com/explore/xxx"

  # 使用 Cookie 登录
  %(prog)s --url "https://www.xiaohongshu.com/explore/xxx" --cookies "name=value"

  # 提取回复
  %(prog)s --url "https://www.xiaohongshu.com/explore/xxx" --ensure_fedback
        """
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        help="小红书内容 URL"
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
        "--cookies",
        default=None,
        help="Cookie 字符串"
    )

    parser.add_argument(
        "--cookies-file",
        default=None,
        help="Cookie 文件路径"
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
        help="禁用无头浏览器"
    )

    args = parser.parse_args()

    # 处理 Cookie
    cookies = None
    if args.cookies_file and os.path.exists(args.cookies_file):
        with open(args.cookies_file, 'r', encoding='utf-8') as f:
            cookies = f.read().strip()
    elif args.cookies:
        cookies = args.cookies

    # 创建爬虫并收集评论
    try:
        with XiaohongshuCollector(headless=args.headless) as collector:
            comments = collector.collect(
                url=args.url,
                max_comments=args.max_comments,
                scroll_times=args.scroll_times,
                ensure_fedback=args.ensure_fedback,
                max_replies=args.max_replies,
                cookies=cookies
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


if __name__ == "__main__":
    main()
