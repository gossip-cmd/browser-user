#!/usr/bin/env python3
"""
Bilibili 扫码登录模块 - 获取并保存 Cookies
"""

import os
import sys
import time
import json
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class BilibiliQRLogin:
    """Bilibili 扫码登录类"""

    def __init__(self, cookie_file: str = "bilibili_cookies.json"):
        self.cookie_file = cookie_file
        self.driver = None

    def _init_driver(self) -> webdriver.Chrome:
        """初始化 Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--window-size=800,600")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def login(self) -> dict:
        """
        执行扫码登录

        Returns:
            登录后的 cookies 字典
        """
        print("[INFO] 启动扫码登录...")
        self.driver = self._init_driver()

        # 访问登录页面
        print("[INFO] 正在打开 Bilibili 登录页面...")
        self.driver.get("https://passport.bilibili.com/login")

        # 等待扫码
        print("\n" + "="*50)
        print("请使用 Bilibili 手机 App 扫描页面上的二维码")
        print("登录成功后，程序会自动获取 Cookie")
        print("="*50 + "\n")

        # 等待登录完成（检查是否跳转或 cookie 出现）
        logged_in = False
        max_wait = 120  # 最多等待 120 秒
        for i in range(max_wait):
            time.sleep(1)

            # 检查是否登录成功
            current_url = self.driver.current_url
            if "bilibili.com" in current_url and "passport" not in current_url:
                logged_in = True
                print(f"[INFO] 检测到页面跳转，登录成功！({i+1}秒)")
                break

            # 检查是否有登录态的 cookie
            cookies = self.driver.get_cookies()
            sessdata = [c for c in cookies if c['name'] == 'SESSDATA']
            if sessdata and sessdata[0].get('value'):
                # 检查是否过期
                if sessdata[0].get('expiry', 0) > time.time():
                    logged_in = True
                    print(f"[INFO] 检测到登录态 Cookie，登录成功！({i+1}秒)")
                    break

            if (i + 1) % 10 == 0:
                print(f"[INFO] 等待扫码... ({i+1}/{max_wait}秒)")

        if not logged_in:
            print("[ERROR] 登录超时，请重试")
            self.close()
            return {}

        # 获取所有 cookies
        time.sleep(2)  # 等待 cookie 稳定
        cookies = self.driver.get_cookies()

        # 转换为字典
        cookie_dict = {c['name']: c['value'] for c in cookies}

        # 保存到文件
        self._save_cookies(cookies)

        # 同时保存为字符串格式
        cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
        self._save_cookie_string(cookie_str)

        print(f"\n[INFO] 成功获取 {len(cookies)} 个 Cookie")
        print(f"[INFO] 用户ID: {cookie_dict.get('DedeUserID', 'unknown')}")

        self.close()
        return cookie_dict

    def _save_cookies(self, cookies: list):
        """保存 cookies 到 JSON 文件"""
        data = {
            'cookies': cookies,
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': None
        }

        # 尝试获取用户ID
        for c in cookies:
            if c['name'] == 'DedeUserID':
                data['user_id'] = c['value']
                break

        with open(self.cookie_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[INFO] Cookies 已保存到: {self.cookie_file}")

    def _save_cookie_string(self, cookie_str: str):
        """保存 cookie 字符串到文本文件"""
        txt_file = self.cookie_file.replace('.json', '.txt')
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(cookie_str)
        print(f"[INFO] Cookie 字符串已保存到: {txt_file}")

    def load_cookies(self) -> str:
        """
        加载已保存的 cookies

        Returns:
            cookie 字符串，如果无效则返回空字符串
        """
        if not os.path.exists(self.cookie_file):
            return ""

        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cookies = data.get('cookies', [])

            # 检查是否过期
            current_time = time.time()
            valid_cookies = []

            for c in cookies:
                expiry = c.get('expiry', 0)
                if expiry == 0 or expiry > current_time:
                    valid_cookies.append(c)

            if len(valid_cookies) < 3:  # 关键 cookie 数量不足
                print("[WARN] Cookie 已过期或无效")
                return ""

            # 构建 cookie 字符串
            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in valid_cookies])

            print(f"[INFO] 成功加载 {len(valid_cookies)} 个有效 Cookie")
            print(f"[INFO] 用户ID: {data.get('user_id', 'unknown')}")
            print(f"[INFO] 上次更新: {data.get('updated_at', 'unknown')}")

            return cookie_str

        except Exception as e:
            print(f"[ERROR] 加载 Cookie 失败: {e}")
            return ""

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bilibili 扫码登录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 扫码登录并保存 Cookie
  python qr_login.py

  # 指定 Cookie 保存路径
  python qr_login.py --output ./my_cookies.json

  # 检查已保存的 Cookie 是否有效
  python qr_login.py --check
        """
    )

    parser.add_argument(
        "--output", "-o",
        default="bilibili_cookies.json",
        help="Cookie 保存路径 (默认: bilibili_cookies.json)"
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="检查已保存的 Cookie 是否有效"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新登录，忽略已保存的 Cookie"
    )

    args = parser.parse_args()

    login = BilibiliQRLogin(cookie_file=args.output)

    # 检查模式
    if args.check:
        cookie_str = login.load_cookies()
        if cookie_str:
            print("\n✓ Cookie 有效")
            sys.exit(0)
        else:
            print("\n✗ Cookie 无效或已过期")
            sys.exit(1)

    # 尝试加载已有 cookie
    if not args.force:
        cookie_str = login.load_cookies()
        if cookie_str:
            print("\n已找到有效的 Cookie，无需重新登录")
            print("使用 --force 参数可以强制重新登录")
            return

    # 执行扫码登录
    cookies = login.login()

    if cookies:
        print("\n" + "="*50)
        print("登录成功！")
        print(f"Cookie 已保存，下次可直接使用")
        print("="*50)
    else:
        print("\n登录失败，请重试")
        sys.exit(1)


if __name__ == "__main__":
    main()
