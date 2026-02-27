# Comment Collector 参考文档

## 目录
1. [Selenium WebDriver 文档](#selenium-webdriver-文档)
2. [常见网站选择器参考](#常见网站选择器参考)
3. [故障排除](#故障排除)
4. [进阶用法](#进阶用法)

---

## Selenium WebDriver 文档

### 官方文档
- [Selenium Python 文档](https://selenium-python.readthedocs.io/)
- [WebDriver 官方文档](https://www.w3.org/TR/webdriver/)
- [ChromeDriver 下载](https://chromedriver.chromium.org/)

### 常用 API

#### 查找元素
```python
# 通过 ID 查找
element = driver.find_element(By.ID, "id")

# 通过 CSS 选择器查找
element = driver.find_element(By.CSS_SELECTOR, ".class")

# 通过 XPath 查找
element = driver.find_element(By.XPATH, "//div[@class='example']")

# 查找多个元素
elements = driver.find_elements(By.CSS_SELECTOR, ".item")
```

#### 等待元素
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 显式等待
element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "myElement"))
)
```

#### 页面操作
```python
# 滚动到元素
driver.execute_script("arguments[0].scrollIntoView();", element)

# 滚动页面
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

# 获取页面源码
html = driver.page_source
```

---

## 常见网站选择器参考

### 视频平台

#### YouTube
```python
# 评论内容
"ytd-comment-thread-renderer #content-text"

# 评论作者
"ytd-comment-thread-renderer #author-text"

# 点赞数
"ytd-comment-thread-renderer #vote-count-middle"
```

#### Bilibili
```python
# 评论内容
".reply-item .reply-content"

# 用户名
".reply-item .user-name"

# 发布时间
".reply-item .reply-time"
```

### 社交媒体

#### 微博
```python
# 评论内容
".list_con .txt"

# 用户
".list_con .W_f14"

# 时间和来源
".list_con .WB_from"
```

#### Twitter/X
```python
# 推文内容
"[data-testid='tweetText']"

# 用户名
"[data-testid='User-Name']"
```

#### Reddit
```python
# 评论内容
"[data-testid='comment']"

# 嵌套评论
".Comment"
```

### 论坛/社区

#### 知乎
```python
# 评论内容
".CommentItemV2-content"

# 评论者
".CommentItemV2-meta"
```

#### V2EX
```python
# 回复内容
".reply_content"

# 回复者
".dark"
```

---

## 故障排除

### 常见问题

#### 1. ChromeDriver 版本不匹配
**错误信息**: `session not created: This version of ChromeDriver only supports Chrome version X`

**解决方案**:
```bash
# 使用 webdriver-manager 自动管理
pip install webdriver-manager
```

#### 2. 元素未找到
**错误信息**: `NoSuchElementException`

**解决方案**:
- 增加等待时间
- 检查选择器是否正确
- 确认元素是否在 iframe 中
- 页面可能需要滚动加载

```python
# 切换到 iframe
iframe = driver.find_element(By.TAG_NAME, "iframe")
driver.switch_to.frame(iframe)

# 切回主文档
driver.switch_to.default_content()
```

#### 3. 被反爬虫检测
**现象**: 页面显示验证码或访问被拒绝

**解决方案**:
```python
# 添加更多浏览器选项
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

# 修改 navigator.webdriver
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
```

#### 4. 页面加载超时
**错误信息**: `TimeoutException`

**解决方案**:
```python
# 设置更长的超时时间
driver.set_page_load_timeout(60)

# 或使用 try-except 处理
try:
    driver.get(url)
except TimeoutException:
    driver.execute_script("window.stop();")
```

---

## 进阶用法

### 自定义收集器

```python
from comment_collector import CommentCollector

class CustomCollector(CommentCollector):
    def _extract_comment(self, element):
        # 自定义提取逻辑
        comment = super()._extract_comment(element)

        # 添加额外字段
        try:
            comment["avatar"] = element.find_element(
                By.CSS_SELECTOR, ".avatar"
            ).get_attribute("src")
        except:
            comment["avatar"] = None

        return comment

# 使用自定义收集器
with CustomCollector() as collector:
    comments = collector.collect(url="https://example.com")
```

### 处理分页

```python
def collect_with_pagination(url, pages=5):
    all_comments = []

    with CommentCollector() as collector:
        for page in range(pages):
            print(f"收集第 {page + 1} 页...")
            comments = collector.collect(url, max_comments=50)
            all_comments.extend(comments)

            # 点击下一页按钮
            try:
                next_btn = collector.driver.find_element(
                    By.CSS_SELECTOR, ".next-page"
                )
                next_btn.click()
                time.sleep(2)
            except:
                break

    return all_comments
```

### 异步收集

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def collect_single(url):
    with CommentCollector(headless=True) as collector:
        return collector.collect(url, max_comments=50)

async def collect_multiple(urls):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = [
            loop.run_in_executor(executor, collect_single, url)
            for url in urls
        ]
        results = await asyncio.gather(*tasks)
    return results
```

---

## 安全与合规

### 注意事项
1. **遵守 robots.txt**: 在爬取前检查目标网站的 robots.txt 文件
2. **控制请求频率**: 添加适当的延迟，避免对服务器造成压力
3. **尊重版权**: 仅将收集的数据用于个人学习或授权用途
4. **隐私保护**: 不要存储或传播用户的敏感信息

### 法律声明
本工具仅供学习和研究使用。使用本工具时请遵守：
- 目标网站的服务条款
- 相关法律法规
- 数据保护条例（如 GDPR）
