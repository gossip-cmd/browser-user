#!/usr/bin/env python3
"""
Bilibili Comment Collector - 专门用于爬取 Bilibili 视频评论
支持：Cookie登录、评论爬取、回复提取
"""

import argparse
import os
import time
from typing import List, Dict, Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from base_collector import BaseCollector


class BilibiliCollector(BaseCollector):
    """Bilibili 评论收集器"""

    def _get_platform_name(self) -> str:
        """获取平台名称"""
        return "bilibili"

    def _get_comment_selector(self) -> str:
        """获取 Bilibili 评论选择器"""
        return ".reply-wrap[data-id]"

    def _wait_for_comments(self):
        """等待 Bilibili 评论加载完成"""
        print("[INFO] 等待 Bilibili 评论加载...")

        # 先滚动到页面底部附近触发评论区域加载
        for scroll_pos in [500, 1000, 1500, 2000]:
            self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
            time.sleep(1)

        # 检测是否需要登录
        try:
            login_tip = self.driver.find_elements(By.CSS_SELECTOR, ".login-tip, .no-login, .need-login")
            if login_tip:
                print("[WARN] 检测到需要登录才能查看完整评论")
                print("[INFO] 尝试获取已显示的评论...")
        except:
            pass

        # 尝试点击"展开更多"或"查看更多"按钮
        clicked = self._click_expand_buttons()

        # 等待评论列表出现 - 增加等待时间和检查频率
        max_wait = 30
        last_count = 0
        stable_count = 0

        for i in range(max_wait):
            reply_wraps = self.driver.find_elements(By.CSS_SELECTOR, ".reply-wrap")
            list_items = self.driver.find_elements(By.CSS_SELECTOR, ".list-item.reply-wrap")
            total = len(reply_wraps) + len(list_items)

            # 检查评论数是否稳定
            if total == last_count:
                stable_count += 1
            else:
                stable_count = 0
                last_count = total

            print(f"[INFO] 等待评论加载... 找到 {total} 个评论元素 ({i+1}/{max_wait})")

            if total >= 5 and stable_count >= 3:
                print(f"[INFO] 评论已稳定加载，共 {total} 条")
                break

            # 如果评论数很少，再次尝试点击展开按钮
            if total < 5 and i > 5 and not clicked:
                clicked = self._click_expand_buttons()

            time.sleep(1)

    def _get_comment_elements(self) -> List:
        """获取 Bilibili 评论元素列表"""
        # 尝试多种选择器
        selectors = [
            ".reply-wrap[data-id]",  # 带data-id的回复
            ".list-item.reply-wrap",  # 列表项
            ".comment-list .reply-wrap",  # 评论列表中的回复
            ".bb-comment .reply-wrap",  # 评论区容器内
        ]

        all_elements = []
        seen_ids = set()

        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"[INFO] 选择器 '{selector}' 找到 {len(elements)} 个元素")
            for elem in elements:
                data_id = elem.get_attribute("data-id")
                if data_id and data_id not in seen_ids:
                    seen_ids.add(data_id)
                    all_elements.append(elem)

        print(f"[INFO] 去重后共 {len(all_elements)} 个评论元素")
        return all_elements

    def _extract_comment(self, element) -> Optional[Dict]:
        """从元素中提取 Bilibili 评论"""
        try:
            # 检查是否是真正的评论项（有 data-id 属性）
            data_id = element.get_attribute("data-id")
            if not data_id:
                return None  # 不是评论项，可能是其他元素

            # 提取用户名 - 尝试多种选择器
            author = ""
            for selector in [".name .username", ".user-name", ".name", "[data-usercard-mid]"]:
                author = self._safe_extract(element, selector)
                if author:
                    break

            # 提取评论内容
            content = ""
            for selector in [".reply-content", ".text", ".content", ".reply-desc"]:
                try:
                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                    content = content_elem.get_attribute("textContent") or content_elem.text
                    if content:
                        break
                except NoSuchElementException:
                    continue

            # 提取时间
            time_str = ""
            for selector in [".reply-time", ".time", ".reply-info time", ".reply-info .reply-time"]:
                time_str = self._safe_extract(element, selector)
                if time_str:
                    break

            # 提取点赞数
            likes = 0
            for selector in [".like span", ".reply-like span", ".reply-action span"]:
                try:
                    like_elem = element.find_element(By.CSS_SELECTOR, selector)
                    like_text = like_elem.get_attribute("textContent") or ""
                    numbers = ''.join(filter(str.isdigit, like_text))
                    if numbers:
                        likes = int(numbers)
                        break
                except NoSuchElementException:
                    continue

            # 如果内容为空，跳过
            if not content or len(content.strip()) < 3:
                return None

            return {
                "author": author.strip(),
                "content": content.strip(),
                "time": time_str.strip(),
                "likes": likes
            }
        except Exception as e:
            print(f"[WARN] 提取Bilibili评论失败: {e}")
            return None

    def _extract_comment_replies(self, comment_element, max_replies: int = 100) -> List[Dict]:
        """提取评论下的回复（Bilibili专用）"""
        replies = []

        try:
            # 首先尝试点击"查看回复"按钮展开所有回复
            clicked = self._click_reply_expand_button(comment_element)

            # 如果点击了展开按钮，等待回复加载
            if clicked:
                print("[INFO] 等待回复加载完成...")
                time.sleep(5)  # 增加等待时间到5秒

                # 检查是否有弹出层（Bilibili有时会打开专门的回复视图）
                popup_replies = self._extract_replies_from_popup()
                if popup_replies:
                    print(f"[INFO] 从弹出层提取到 {len(popup_replies)} 条回复")
                    return popup_replies[:max_replies]

                # 持续点击"查看更多"直到没有更多回复
                last_reply_count = 0
                no_change_count = 0
                for load_attempt in range(20):  # 最多尝试20次
                    # 统计当前回复数量
                    current_replies = comment_element.find_elements(
                        By.CSS_SELECTOR,
                        ".sub-reply-item, .sub-reply-container .sub-reply-item, .reply-item"
                    )
                    current_count = len(current_replies)

                    if current_count > last_reply_count:
                        print(f"[INFO] 回复加载进度: {last_reply_count} -> {current_count} 条")
                        last_reply_count = current_count
                        no_change_count = 0
                    else:
                        no_change_count += 1
                        if no_change_count >= 3:
                            print(f"[INFO] 没有更多回复可加载，共 {current_count} 条")
                            break

                    # 点击后重新查找评论元素，因为DOM可能已更新
                    updated_comment = self._find_updated_comment_element(comment_element)
                    if updated_comment:
                        comment_element = updated_comment

                    # 尝试加载更多
                    loaded = self._load_all_replies(comment_element)
                    if not loaded:
                        break

                    time.sleep(1)  # 等待加载

            # 再次检查弹出层（可能在加载后出现）
            popup_replies = self._extract_replies_from_popup()
            if popup_replies:
                print(f"[INFO] 从弹出层提取到 {len(popup_replies)} 条回复")
                return popup_replies[:max_replies]

            # 在整个页面范围内查找回复（展开后回复可能在页面级别）
            page_replies = self._extract_replies_from_page()
            if page_replies and len(page_replies) > len(replies):
                print(f"[INFO] 从页面级别提取到 {len(page_replies)} 条回复")
                return page_replies[:max_replies]

            # 查找回复容器 - 使用更通用的选择器
            reply_container_selectors = [
                ".sub-reply-item",  # Bilibili子回复项
                ".sub-reply-list > div",  # 子回复列表的直接子元素
                ".reply-item[data-id]",  # 回复项（带data-id）
                ".reply-container .reply-item",  # 回复容器中的项
                ".sub-reply-container .sub-reply-item",  # 子回复容器中的项
            ]

            reply_elements = []
            for selector in reply_container_selectors:
                try:
                    # 在当前评论元素下查找回复
                    elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        # 去重：使用data-id或文本内容
                        seen_ids = set()
                        seen_texts = set()
                        unique_elements = []
                        for elem in elements:
                            data_id = elem.get_attribute("data-id")
                            text = elem.text or ""
                            # 使用data-id或文本去重
                            key = data_id if data_id else text[:50]
                            if key and key not in seen_ids and key not in seen_texts:
                                if data_id:
                                    seen_ids.add(data_id)
                                else:
                                    seen_texts.add(text[:50])
                                unique_elements.append(elem)

                        if len(unique_elements) > len(reply_elements):
                            reply_elements = unique_elements
                            print(f"[DEBUG] 使用选择器 {selector} 找到 {len(unique_elements)} 个回复")
                except Exception as e:
                    continue

            print(f"[DEBUG] 总共找到 {len(reply_elements)} 个唯一回复元素")

            # 如果找到回复容器，提取每个回复
            for idx, reply_elem in enumerate(reply_elements[:max_replies]):
                reply = self._extract_single_reply(reply_elem)
                if reply and reply.get("content"):
                    reply["index"] = idx + 1
                    replies.append(reply)

            print(f"[INFO] 成功提取 {len(replies)} 条回复")
            return replies

        except Exception as e:
            print(f"[WARN] 提取回复失败: {e}")
            return replies

    def _click_expand_buttons(self) -> bool:
        """尝试点击展开/查看更多按钮"""
        # Bilibili特定的回复展开按钮选择器（按优先级排序）
        expand_selectors = [
            ".reply-box .view-more a",  # 回复框中的查看链接
            ".reply-box .view-more",    # 回复框中的查看更多
            ".sub-reply-box .view-more",  # 子回复框中的查看更多
            ".view-more",  # 通用的查看更多
            ".reply-more",  # 更多回复
            ".show-more",  # 显示更多
            ".expand-btn",  # 展开按钮
            ".fold-btn",  # 折叠按钮
            ".fetch-more",  # 获取更多
            ".load-more-comment",  # 加载更多评论
            ".more-comment",  # 更多评论
            "[class*='view-more']",
            "[class*='show-more']",
            "[class*='fetch-more']",
            "button[class*='more']",
            "div[class*='more-comment']",
            "a[href='javascript:void(0)']",  # 可能是点击查看链接
        ]

        clicked_any = False
        clicked_count = 0

        for selector in expand_selectors:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed():
                        text = btn.text or btn.get_attribute("textContent") or ""
                        # 检查是否包含回复相关文字
                        if any(kw in text for kw in ["更多", "展开", "查看", "加载", "回复", "条"]):
                            # 滚动到按钮（使用 nearest 而不是 center，避免滚动过多）
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});",
                                btn
                            )
                            time.sleep(0.3)

                            try:
                                # 优先尝试普通点击
                                btn.click()
                                clicked_count += 1
                                print(f"[INFO] 点击展开按钮 ({clicked_count}): {text[:40]}")
                            except Exception:
                                # 如果普通点击失败，使用JS点击
                                try:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    clicked_count += 1
                                    print(f"[INFO] JS点击展开按钮 ({clicked_count}): {text[:40]}")
                                except Exception as e2:
                                    print(f"[WARN] 点击按钮失败: {e2}")
                                    continue

                            clicked_any = True
                            time.sleep(1.5)  # 等待内容加载

                            # 限制点击次数，避免过多点击
                            if clicked_count >= 20:
                                return clicked_any
            except Exception as e:
                continue

        return clicked_any

    def _click_reply_expand_button(self, comment_element):
        """点击评论的"查看回复"按钮"""
        # 查看回复的按钮选择器
        reply_expand_selectors = [
            ".reply-box .view-more",  # 回复框中的查看更多
            ".reply-more",  # 更多回复
            "a[href*='#reply']",  # 回复链接
            "[class*='fold']",  # 折叠按钮
            ".sub-reply-box .view-more",  # 子回复框中的查看更多
        ]

        for selector in reply_expand_selectors:
            try:
                buttons = comment_element.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        text = btn.text or btn.get_attribute("textContent") or ""
                        if any(kw in text for kw in ["回复", "查看", "展开", "更多"]):
                            # 滚动到按钮
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'nearest'});",
                                btn
                            )
                            time.sleep(0.3)

                            try:
                                btn.click()
                                print(f"[INFO] 点击查看回复: {text[:40]}")
                                return True
                            except:
                                try:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    print(f"[INFO] JS点击查看回复: {text[:40]}")
                                    return True
                                except:
                                    pass
            except:
                continue

        return False

    def _extract_replies_from_popup(self) -> List[Dict]:
        """从弹出层中提取回复（Bilibili有时会打开专门的回复视图）"""
        replies = []

        # 弹出层选择器
        popup_selectors = [
            ".reply-popup",  # 回复弹出层
            ".sub-reply-popup",  # 子回复弹出层
            ".reply-dialog",  # 回复对话框
            ".reply-detail",  # 回复详情
            ".sub-reply-detail",  # 子回复详情
            "[class*='popup']",  # 任何弹出层
            "[class*='dialog']",  # 任何对话框
        ]

        for selector in popup_selectors:
            try:
                popups = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for popup in popups:
                    if popup.is_displayed():
                        print(f"[INFO] 发现回复弹出层: {selector}")

                        # 在弹出层中查找并点击"查看更多"按钮
                        self._load_more_in_popup(popup)

                        # 在弹出层中查找回复
                        reply_selectors = [
                            ".sub-reply-item",
                            ".reply-item",
                            ".sub-comment-item",
                            ".reply-content",  # 直接查找回复内容
                        ]

                        for reply_selector in reply_selectors:
                            reply_elements = popup.find_elements(By.CSS_SELECTOR, reply_selector)
                            if reply_elements:
                                print(f"[INFO] 在弹出层中找到 {len(reply_elements)} 条回复")
                                for idx, elem in enumerate(reply_elements):
                                    reply = self._extract_single_reply(elem)
                                    if reply and reply.get("content"):
                                        reply["index"] = idx + 1
                                        replies.append(reply)

                        # 关闭弹出层（如果有关闭按钮）
                        try:
                            close_btns = popup.find_elements(By.CSS_SELECTOR, ".close, .close-btn, [class*='close']")
                            for close_btn in close_btns:
                                if close_btn.is_displayed():
                                    close_btn.click()
                                    time.sleep(1)
                                    break
                        except:
                            pass

                        return replies
            except:
                continue

        return replies

    def _load_more_in_popup(self, popup_element):
        """在弹出层中点击"查看更多"加载更多回复"""
        load_more_selectors = [
            ".view-more",
            ".load-more",
            ".show-more",
            ".fetch-more",
            "[class*='view-more']",
            "[class*='load-more']",
        ]

        for selector in load_more_selectors:
            try:
                buttons = popup_element.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed():
                        text = btn.text or btn.get_attribute("textContent") or ""
                        if any(kw in text for kw in ["更多", "查看", "加载"]):
                            try:
                                btn.click()
                                print(f"[INFO] 在弹出层中点击: {text[:40]}")
                                time.sleep(2)
                                found = True
                                break
                            except:
                                pass
            except:
                continue

    def _find_updated_comment_element(self, original_element):
        """在DOM更新后重新查找评论元素"""
        try:
            # 获取原评论的data-id
            data_id = original_element.get_attribute("data-id")
            if not data_id:
                return None

            # 重新查找具有相同data-id的评论
            comments = self.driver.find_elements(By.CSS_SELECTOR, ".reply-wrap[data-id]")
            for comment in comments:
                if comment.get_attribute("data-id") == data_id:
                    return comment

            return None
        except:
            return None

    def _extract_replies_from_page(self) -> List[Dict]:
        """在整个页面范围内查找回复（用于展开后回复在页面级别的情况）"""
        replies = []

        # 在页面级别查找回复
        reply_selectors = [
            ".sub-reply-item",
            ".reply-detail .reply-item",
            ".sub-reply-container .sub-reply-item",
            ".reply-popup .reply-item",
        ]

        for selector in reply_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"[DEBUG] 在页面级别找到 {len(elements)} 条回复 ({selector})")

                    # 去重
                    seen_texts = set()
                    for elem in elements:
                        reply = self._extract_single_reply(elem)
                        if reply and reply.get("content"):
                            # 使用内容前50字符去重
                            key = reply["content"][:50]
                            if key not in seen_texts:
                                seen_texts.add(key)
                                reply["index"] = len(replies) + 1
                                replies.append(reply)

                    if replies:
                        break
            except Exception as e:
                continue

        return replies

    def _load_all_replies(self, comment_element):
        """持续加载所有回复，支持分页机制"""
        total_replies = 0

        # 首先尝试翻页加载
        page_loaded = self._load_replies_by_pagination(comment_element)

        if not page_loaded:
            # 如果没有分页控件，使用原来的加载更多逻辑
            total_replies = self._load_replies_by_click(comment_element)
        else:
            # 统计分页加载后的回复数量
            final_replies = comment_element.find_elements(By.CSS_SELECTOR, ".sub-reply-item, .reply-item, .sub-reply-container .sub-reply-item")
            total_replies = len(final_replies)

        return total_replies

    def _load_replies_by_pagination(self, comment_element) -> bool:
        """通过翻页加载所有回复，返回是否使用了分页"""
        # 分页控件选择器
        pagination_selectors = [
            ".reply-pagination",  # 分页容器
            ".pagination",  # 通用分页
            ".paging-box",  # Bilibili分页盒子
            ".page-jump",  # 页码跳转
            ".sub-reply-pagination",  # 子回复分页
        ]

        # 检查是否存在分页控件
        has_pagination = False
        pagination_elem = None
        for selector in pagination_selectors:
            try:
                pagination = comment_element.find_elements(By.CSS_SELECTOR, selector)
                if pagination:
                    has_pagination = True
                    pagination_elem = pagination[0]
                    print(f"[INFO] 发现分页控件: {selector}")
                    break
            except:
                continue

        if not has_pagination:
            return False

        # 获取分页信息
        try:
            # 查找页码按钮
            page_btns = pagination_elem.find_elements(By.CSS_SELECTOR, "button, .page-item, .pagination-btn")
            total_pages = 1
            for btn in page_btns:
                text = btn.text or ""
                if text.isdigit():
                    total_pages = max(total_pages, int(text))

            print(f"[INFO] 分页控件显示共 {total_pages} 页")
        except Exception as e:
            print(f"[WARN] 获取分页信息失败: {e}")
            total_pages = 1

        # 翻页加载所有回复
        all_replies = []
        visited_pages = set()
        max_pages = min(total_pages, 100)  # 最多翻100页

        for page_num in range(1, max_pages + 1):
            # 记录当前页的回复
            current_replies = comment_element.find_elements(
                By.CSS_SELECTOR,
                ".sub-reply-item, .sub-reply-container .sub-reply-item, .reply-item"
            )
            print(f"[INFO] 第 {page_num}/{max_pages} 页，当前有 {len(current_replies)} 条回复")

            if page_num >= max_pages:
                print(f"[INFO] 已翻到最后一页")
                break

            # 查找页码按钮区域（在评论元素内或整个页面）
            try:
                # 首先尝试在评论元素内查找分页
                page_container = comment_element.find_element(
                    By.CSS_SELECTOR,
                    ".reply-pagination, .pagination, .paging-box"
                )
            except:
                # 如果找不到，可能在页面级别
                page_container = self.driver

            # 查找下一页按钮或指定页码按钮
            next_page_found = False
            try:
                # 查找所有可能的页码按钮
                page_buttons = page_container.find_elements(
                    By.CSS_SELECTOR,
                    "button, .page-item, .pagination-btn, .paging-item"
                )

                for btn in page_buttons:
                    btn_text = (btn.text or "").strip()
                    # 检查是否是下一页按钮或下一页的页码
                    if btn_text == str(page_num + 1) or btn_text in ["下一页", ">", "›"]:
                        if btn.is_displayed():
                            # 检查是否已经访问过
                            btn_id = btn.get_attribute("data-page") or btn_text
                            if btn_id in visited_pages:
                                continue
                            visited_pages.add(btn_id)

                            # 滚动到按钮并点击
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                btn
                            )
                            time.sleep(0.5)

                            try:
                                btn.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)

                            print(f"[INFO] 点击第 {page_num + 1} 页")
                            time.sleep(3)  # 等待页面加载
                            next_page_found = True
                            break
            except Exception as e:
                print(f"[WARN] 查找下一页按钮失败: {e}")

            if not next_page_found:
                print(f"[INFO] 没有找到下一页按钮，停止翻页")
                break

        return True

    def _load_replies_by_click(self, comment_element):
        """通过点击"查看更多"按钮加载回复"""
        load_more_count = 0
        max_attempts = 50

        for attempt in range(max_attempts):
            # 统计当前回复数量
            current_replies = comment_element.find_elements(
                By.CSS_SELECTOR,
                ".sub-reply-item, .sub-reply-container .sub-reply-item, .reply-item"
            )
            print(f"[DEBUG] 当前回复数: {len(current_replies)}")

            # 尝试找到并点击"查看更多"按钮
            found_more = False
            more_selectors = [
                ".reply-box .view-more",  # Bilibili 回复框中的查看更多
                ".reply-more",  # 更多回复
                ".view-more",  # 通用查看更多
                ".fetch-more",  # 获取更多
                "[class*='view-more']",
                "[class*='fetch-more']",
            ]

            for selector in more_selectors:
                try:
                    buttons = comment_element.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            text = btn.text or btn.get_attribute("textContent") or ""
                            if any(kw in text for kw in ["更多", "查看", "回复", "条"]):
                                # 滚动到按钮
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'nearest'});",
                                    btn
                                )
                                time.sleep(0.3)

                                try:
                                    btn.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", btn)

                                print(f"[DEBUG] 点击查看更多: {text[:40]}")
                                time.sleep(1)
                                load_more_count += 1
                                found_more = True
                                break
                except:
                    continue

            if not found_more:
                print(f"[DEBUG] 未找到更多按钮")
                break

            if load_more_count >= 20:
                print(f"[DEBUG] 已点击20次，停止加载")
                break

        return load_more_count

    def _extract_single_reply(self, reply_element) -> Optional[Dict]:
        """提取单条回复信息"""
        try:
            # 提取回复用户名
            author = ""
            for selector in [".name .username", ".user-name", ".name", "[data-usercard-mid]"]:
                author = self._safe_extract(reply_element, selector)
                if author:
                    break

            # 提取回复内容
            content = ""
            for selector in [".reply-content", ".text", ".content", ".reply-desc"]:
                try:
                    content_elem = reply_element.find_element(By.CSS_SELECTOR, selector)
                    content = content_elem.get_attribute("textContent") or content_elem.text
                    if content:
                        break
                except NoSuchElementException:
                    continue

            # 提取回复时间
            time_str = ""
            for selector in [".reply-time", ".time", ".reply-info time"]:
                time_str = self._safe_extract(reply_element, selector)
                if time_str:
                    break

            # 提取点赞数
            likes = 0
            for selector in [".like span", ".reply-like span", ".reply-action span"]:
                try:
                    like_elem = reply_element.find_element(By.CSS_SELECTOR, selector)
                    like_text = like_elem.get_attribute("textContent") or ""
                    numbers = ''.join(filter(str.isdigit, like_text))
                    if numbers:
                        likes = int(numbers)
                        break
                except NoSuchElementException:
                    continue

            # 如果内容为空，返回None
            if not content or len(content.strip()) < 2:
                return None

            return {
                "author": author.strip(),
                "content": content.strip(),
                "time": time_str.strip(),
                "likes": likes
            }
        except Exception as e:
            print(f"[WARN] 提取回复失败: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Bilibili Comment Collector - 爬取 Bilibili 视频评论",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 自动登录（需要先执行 qr_login.py）
  %(prog)s --url "https://www.bilibili.com/video/BVxxx" --auto-login

  # 使用 Cookie 登录
  %(prog)s --url "https://www.bilibili.com/video/BVxxx" --cookies "name=value; name2=value2"

  # 提取回复
  %(prog)s --url "https://www.bilibili.com/video/BVxxx" --auto-login --ensure_fedback
        """
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        help="Bilibili 视频 URL"
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
        help="Cookie 字符串（格式：name=value; name2=value2）"
    )

    parser.add_argument(
        "--cookies-file",
        default=None,
        help="Cookie 文件路径"
    )

    parser.add_argument(
        "--auto-login",
        action="store_true",
        help="自动加载保存的 Cookie（需要先执行 qr_login.py）"
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
    if args.auto_login:
        # 从 qr_login.py 生成的文件读取 Cookie
        default_cookie_file = "bilibili_cookies.txt"
        if os.path.exists(default_cookie_file):
            with open(default_cookie_file, 'r', encoding='utf-8') as f:
                cookies = f.read().strip()
    elif args.cookies_file and os.path.exists(args.cookies_file):
        with open(args.cookies_file, 'r', encoding='utf-8') as f:
            cookies = f.read().strip()
    elif args.cookies:
        cookies = args.cookies

    # 创建爬虫并收集评论
    try:
        with BilibiliCollector(headless=args.headless) as collector:
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
