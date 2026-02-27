#!/usr/bin/env python3
"""
Generic SNS Comment Collector - 用于爬取各类社交媒体评论
支持：通用社交媒体平台（Reddit、Telegram、Discord 等）
"""

import argparse
import time
from typing import List, Dict, Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from base_collector import BaseCollector


class SNSCollector(BaseCollector):
    """通用社交媒体评论收集器"""

    def _get_platform_name(self) -> str:
        """获取平台名称"""
        return "sns"

    def _get_comment_selector(self) -> str:
        """获取评论选择器"""
        return "[class*='Comment'], [class*='comment'], [data-testid='comment'], .post, .reply"

    def _wait_for_comments(self):
        """等待评论加载完成"""
        print("[INFO] 等待 SNS 评论加载...")

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
        """获取评论元素列表"""
        selectors = [
            "[class*='Comment']",
            "[class*='comment']",
            "[data-testid='comment']",
            ".post",
            ".reply",
            "[role='article']",
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
        """从元素中提取评论"""
        try:
            # 提取用户名（尝试多种选择器）
            author = ""
            for selector in [
                "a[href*='/user']",
                "a[href*='/profile']",
                "[class*='username']",
                "[class*='author']",
                "span[class*='name']",
            ]:
                try:
                    author_elem = element.find_element(By.CSS_SELECTOR, selector)
                    author = (author_elem.get_attribute("textContent") or author_elem.text or "").strip()
                    if author and len(author) > 1:
                        break
                except NoSuchElementException:
                    continue

            # 提取评论内容
            content = ""
            for selector in [
                "[class*='content']",
                "[class*='body']",
                "[class*='text']",
                "p",
                "div[class*='message']",
            ]:
                try:
                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                    content = (content_elem.get_attribute("textContent") or content_elem.text or "").strip()
                    if content and len(content) > 2:
                        break
                except NoSuchElementException:
                    continue

            # 提取发布时间
            time_str = ""
            for selector in [
                "time",
                "[class*='time']",
                "[class*='date']",
                "a[title*='ago']",
            ]:
                try:
                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                    time_str = (time_elem.get_attribute("title") or
                               time_elem.get_attribute("textContent") or
                               time_elem.text or "").strip()
                    if time_str:
                        break
                except NoSuchElementException:
                    continue

            # 提取互动数（点赞、点踩等）
            interactions = 0
            for selector in [
                "[class*='like']",
                "[class*='upvote']",
                "[class*='score']",
                "button[class*='vote']",
            ]:
                try:
                    int_elem = element.find_element(By.CSS_SELECTOR, selector)
                    int_text = int_elem.get_attribute("aria-label") or int_elem.get_attribute("textContent") or int_elem.text or ""
                    numbers = ''.join(filter(str.isdigit, int_text))
                    if numbers:
                        interactions = int(numbers)
                        break
                except (NoSuchElementException, ValueError):
                    continue

            # 如果内容为空，跳过
            if not content or len(content.strip()) < 2:
                return None

            return {
                "author": author,
                "content": content,
                "time": time_str,
                "likes": interactions
            }
        except Exception as e:
            print(f"[WARN] 提取评论失败: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="SNS Comment Collector - 爬取各类社交媒体评论",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的平台: Reddit, Telegram, Discord, HackerNews 等

示例:
  # Reddit
  %(prog)s --url "https://reddit.com/r/subreddit/comments/abc123"

  # HackerNews
  %(prog)s --url "https://news.ycombinator.com/item?id=12345"
        """
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        help="SNS 帖子/讨论 URL"
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

    # 创建爬虫并收集评论
    try:
        with SNSCollector(headless=args.headless) as collector:
            comments = collector.collect(
                url=args.url,
                max_comments=args.max_comments,
                scroll_times=args.scroll_times
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
