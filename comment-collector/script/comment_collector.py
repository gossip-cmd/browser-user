#!/usr/bin/env python3
"""
Comment Collector - 统一的评论爬虫入口，支持多个平台
通过 URL 自动检测平台，并调用对应的专用爬虫

支持平台：
- Bilibili (哔哩哔哩)
- YouTube (YouTube Shorts)
- Xiaohongshu (小红书)
- TikTok
- Douyin (抖音)
- Twitter/X
- Facebook
- Instagram
- Generic SNS (Reddit, Telegram, Discord, HackerNews等)
"""

import argparse
import os
import sys
from urllib.parse import urlparse

# 导入所有平台的爬虫
from comment_bilibili import BilibiliCollector
from comment_youtube import YoutubeCollector
from comment_xiaohongshu import XiaohongshuCollector
from comment_tiktok import TiktokCollector
from comment_douyin import DouyinCollector
from comment_twitter import TwitterCollector
from comment_facebook import FacebookCollector
from comment_instagram import InstagramCollector
from comment_sns import SNSCollector


def detect_platform(url: str) -> str:
    """根据 URL 检测平台类型

    Args:
        url: 目标 URL

    Returns:
        平台名称: bilibili, youtube, xiaohongshu, tiktok, douyin, twitter, facebook, instagram, sns
    """
    domain = urlparse(url).netloc.lower()

    # 按优先级检测
    platform_map = {
        'bilibili': ['bilibili.com', 'b23.tv'],
        'youtube': ['youtube.com', 'youtu.be'],
        'xiaohongshu': ['xiaohongshu.com', 'xhs.com', 'redbook.com'],
        'tiktok': ['tiktok.com', 'vt.tiktok.com'],
        'douyin': ['douyin.com', 'dy.com'],
        'twitter': ['twitter.com', 'x.com'],
        'facebook': ['facebook.com', 'fb.com'],
        'instagram': ['instagram.com'],
        'sns': ['reddit.com', 'ycombinator.com', 'discord.com', 'telegram.org'],
    }

    for platform, domains in platform_map.items():
        if any(d in domain for d in domains):
            print(f"[INFO] 检测到平台: {platform}")
            return platform

    print("[WARN] 未能检测到平台，使用 SNS 通用爬虫")
    return "sns"


def main():
    parser = argparse.ArgumentParser(
        description="Comment Collector - 多平台评论爬虫（支持 Bilibili、YouTube、小红书、TikTok、抖音）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Bilibili - 自动登录
  %(prog)s --url "https://www.bilibili.com/video/BVxxx" --auto-login

  # YouTube Shorts
  %(prog)s --url "https://www.youtube.com/shorts/abc123"

  # 小红书 - 提取回复
  %(prog)s --url "https://www.xiaohongshu.com/explore/xxx" --ensure_fedback

  # TikTok
  %(prog)s --url "https://www.tiktok.com/@user/video/123456"

  # 抖音
  %(prog)s --url "https://www.douyin.com/video/123456789"
        """
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        help="要爬取评论的目标 URL"
    )

    parser.add_argument(
        "--selector", "-s",
        default=None,
        help="评论元素的 CSS 选择器 (默认自动检测)"
    )

    parser.add_argument(
        "--output", "-o",
        default="comments.json",
        help="输出文件路径 (默认: comments.json)"
    )

    parser.add_argument(
        "--max_comments", "-m",
        type=int,
        default=100,
        help="最大爬取评论数量 (默认: 100)"
    )

    parser.add_argument(
        "--scroll_times",
        type=int,
        default=5,
        help="滚动加载次数 (默认: 5)"
    )

    parser.add_argument(
        "--cookies",
        default=None,
        help="Cookie 字符串 (格式: name=value; name2=value2)"
    )

    parser.add_argument(
        "--cookies-file",
        default=None,
        help="从文件读取 Cookie"
    )

    parser.add_argument(
        "--auto-login",
        action="store_true",
        help="自动加载保存的 Cookie (Bilibili 专用)"
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
        help="每条评论的最大回复数 (默认: 100)"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头浏览器 (默认启用)"
    )

    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="禁用无头浏览器"
    )

    args = parser.parse_args()

    # 检测平台
    platform = detect_platform(args.url)

    # 处理 Cookie
    cookies = None
    if args.auto_login and platform == "bilibili":
        # 从 qr_login.py 生成的文件读取 Cookie
        default_cookie_file = "bilibili_cookies.txt"
        if os.path.exists(default_cookie_file):
            with open(default_cookie_file, 'r', encoding='utf-8') as f:
                cookies = f.read().strip()
            print(f"[INFO] 从 {default_cookie_file} 读取 Cookie")
    elif args.cookies_file and os.path.exists(args.cookies_file):
        with open(args.cookies_file, 'r', encoding='utf-8') as f:
            cookies = f.read().strip()
        print(f"[INFO] 从 {args.cookies_file} 读取 Cookie")
    elif args.cookies:
        cookies = args.cookies

    # 选择对应的爬虫
    collector_class = None
    if platform == "bilibili":
        collector_class = BilibiliCollector
    elif platform == "youtube":
        collector_class = YoutubeCollector
    elif platform == "xiaohongshu":
        collector_class = XiaohongshuCollector
    elif platform == "tiktok":
        collector_class = TiktokCollector
    elif platform == "douyin":
        collector_class = DouyinCollector
    elif platform == "twitter":
        collector_class = TwitterCollector
    elif platform == "facebook":
        collector_class = FacebookCollector
    elif platform == "instagram":
        collector_class = InstagramCollector
    elif platform == "sns":
        collector_class = SNSCollector
    else:
        print("[ERROR] 不支持的平台或无法检测")
        sys.exit(1)

    # 创建爬虫并收集评论
    try:
        print(f"[INFO] 使用 {platform.upper()} 爬虫...")
        with collector_class(headless=args.headless) as collector:
            comments = collector.collect(
                url=args.url,
                selector=args.selector,
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
                print(f"[INFO] 评论已保存到: {args.output}")
            else:
                print("\n[ERROR] 未爬取到任何评论")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断爬取")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 爬取失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
