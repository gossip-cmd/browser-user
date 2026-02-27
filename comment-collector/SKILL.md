# Comment Collector Skill

## 描述
多平台评论爬虫，支持自动检测 URL 平台并调用对应爬虫。使用 WebDriver 自动访问指定 URL，爬取评论内容。

### 支持的平台
- **Bilibili** (哔哩哔哩)：支持登录、评论爬取、回复提取
- **YouTube (Shorts)**：支持公开视频评论爬取
- **Xiaohongshu** (小红书)：支持评论爬取、回复提取
- **TikTok**：支持评论爬取
- **Douyin** (抖音)：支持评论爬取、回复提取

## 使用方法

### 通用参数
- `url` (必需): 要爬取评论的目标 URL
- `output` (可选): 输出文件路径，默认为 `comments.json`
- `max_comments` (可选): 最大爬取评论数量，默认为 100
- `scroll_times` (可选): 页面滚动次数，用于加载更多评论，默认为 5
- `ensure_fedback` (可选): 提取每条评论下的所有回复内容
- `max_replies` (可选): 每条评论最多提取的回复数量，默认为 100
- `headless` (可选): 使用无头浏览器，默认启用
- `no-headless` (可选): 禁用无头浏览器，显示浏览器窗口

### 平台特定参数
#### Bilibili
- `cookies`: Cookie 字符串
- `cookies-file`: 从文件读取 Cookie
- `auto-login`: 自动加载保存的 Cookie

#### YouTube、Xiaohongshu、Douyin
- `cookies`: Cookie 字符串（可选）
- `cookies-file`: 从文件读取 Cookie（可选）

### 基本示例
```bash
# 自动检测平台并爬取评论
python script/comment_collector.py --url "https://example.com/post/123"

# 指定输出和最大评论数
python script/comment_collector.py --url "https://example.com/post/123" \
    --output "output.json" \
    --max_comments 50
```

## 平台特定使用示例

### Bilibili
```bash
# 使用 Cookie 直接登录
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --cookies "buvid3=xxx; SESSDATA=xxx"

# 从文件读取 Cookie
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --cookies-file bilibili_cookies.txt

# 自动登录（使用 qr_login.py 保存的 Cookie）
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --auto-login

# 提取评论及其回复
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --auto-login \
    --ensure_fedback \
    --max_replies 50
```

### YouTube Shorts
```bash
# 基本用法（无需登录）
python script/comment_youtube.py \
    --url "https://www.youtube.com/shorts/abc123"

# 提取评论及回复
python script/comment_youtube.py \
    --url "https://www.youtube.com/shorts/abc123" \
    --ensure_fedback \
    --max_comments 100
```

### 小红书 (Xiaohongshu)
```bash
# 基本用法
python script/comment_xiaohongshu.py \
    --url "https://www.xiaohongshu.com/explore/xxx"

# 使用 Cookie 登录并提取回复
python script/comment_xiaohongshu.py \
    --url "https://www.xiaohongshu.com/explore/xxx" \
    --cookies "..." \
    --ensure_fedback \
    --max_replies 50
```

### TikTok
```bash
# 基本用法
python script/comment_tiktok.py \
    --url "https://www.tiktok.com/@username/video/123456"

# 指定最大评论数
python script/comment_tiktok.py \
    --url "https://www.tiktok.com/@username/video/123456" \
    --max_comments 200
```

### 抖音 (Douyin)
```bash
# 基本用法
python script/comment_douyin.py \
    --url "https://www.douyin.com/video/123456789"

# 提取评论及回复
python script/comment_douyin.py \
    --url "https://www.douyin.com/video/123456789" \
    --ensure_fedback \
    --max_replies 50
```

## 登录支持

对于需要登录才能查看完整评论的网站（如 Bilibili、小红书、抖音），提供两种登录方式：

### 方式1: 使用 Cookie 字符串（快速）
```bash
# 直接传入 Cookie（从浏览器开发者工具复制）
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --cookies "buvid3=xxx; SESSDATA=xxx; bili_jct=xxx"
```

### 方式2: 从文件读取 Cookie
```bash
# 先将 Cookie 保存到文件
echo "buvid3=xxx; SESSDATA=xxx" > bilibili_cookies.txt

# 然后使用文件
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --cookies-file bilibili_cookies.txt
```

### 方式3: 扫码登录 (Bilibili 推荐)
```bash
# 第一步: 扫码登录并自动保存 Cookie
python script/qr_login.py

# 第二步: 使用保存的 Cookie 自动登录爬取
python script/comment_bilibili.py \
    --url "https://www.bilibili.com/video/BVxxx" \
    --auto-login
```

扫码登录工具会自动打开浏览器显示二维码，使用手机 Bilibili App 扫描后即可保存 Cookie，下次直接使用无需再次扫码。

## 依赖
- Python 3.8+
- selenium
- webdriver-manager

## 安装依赖
```bash
pip install selenium webdriver-manager
```

## 架构说明

### 多平台架构
项目采用模块化设计，支持轻松添加新平台：

```
comment-collector/script/
├── base_collector.py          # 通用基类（WebDriver 初始化、Cookie 管理等）
├── comment_collector.py        # 自动检测平台并调用对应爬虫（兼容层）
├── comment_bilibili.py         # Bilibili 专用爬虫
├── comment_youtube.py          # YouTube 专用爬虫
├── comment_xiaohongshu.py      # 小红书专用爬虫
├── comment_tiktok.py           # TikTok 专用爬虫
├── comment_douyin.py           # 抖音专用爬虫
└── qr_login.py                 # Bilibili 扫码登录工具
```

### 设计特点
1. **通用基类**: `BaseCollector` 提供所有平台共用的功能（WebDriver 管理、Cookie 处理、页面滚动等）
2. **平台特定**: 每个平台都是 `BaseCollector` 的子类，实现平台特定的评论提取逻辑
3. **自动检测**: `comment_collector.py` 根据 URL 自动检测平台并调用对应爬虫
4. **向后兼容**: 保留原有的 `comment_collector.py` 接口，确保现有脚本继续工作

## 支持的网站

### 已优化支持的网站
- **Bilibili**: 支持登录后爬取完整评论，自动处理"展开回复"
- **YouTube**: 支持 Shorts 评论区提取
- **小红书**: 支持评论爬取和回复提取
- **TikTok**: 支持评论爬取
- **抖音**: 支持评论爬取和回复提取

## 输出格式

### 基础格式
```json
{
  "metadata": {
    "collected_at": "2026-02-27T20:00:00",
    "total_count": 10,
    "platform": "bilibili"
  },
  "comments": [
    {
      "index": 1,
      "author": "用户名",
      "content": "评论内容",
      "time": "2018-04-06 00:15",
      "likes": 1721
    }
  ]
}
```

### 带回复的格式 (--ensure_fedback)
```json
{
  "metadata": {
    "collected_at": "2026-02-27T20:00:00",
    "total_count": 10,
    "platform": "bilibili"
  },
  "comments": [
    {
      "index": 1,
      "author": "用户名",
      "content": "评论内容",
      "time": "2018-04-06 00:15",
      "likes": 1721,
      "replies": [
        {
          "index": 1,
          "author": "回复者",
          "content": "回复内容",
          "time": "2018-04-06 12:00",
          "likes": 10
        }
      ]
    }
  ]
}
```

## 文件结构
```
comment-collector/
├── SKILL.md                      # 本说明文档
├── script/
│   ├── base_collector.py         # 通用基类
│   ├── comment_collector.py      # 主入口（自动检测并调用平台爬虫）
│   ├── comment_bilibili.py       # Bilibili 爬虫
│   ├── comment_youtube.py        # YouTube 爬虫
│   ├── comment_xiaohongshu.py    # 小红书爬虫
│   ├── comment_tiktok.py         # TikTok 爬虫
│   ├── comment_douyin.py         # 抖音爬虫
│   └── qr_login.py               # Bilibili 扫码登录工具
└── reference/
    └── README.md                 # 详细参考文档
```

## 故障排查

### 评论未加载
- **症状**: 返回 0 条评论
- **解决方案**:
  1. 尝试禁用无头模式查看浏览器实际情况：`--no-headless`
  2. 增加滚动次数：`--scroll_times 10`
  3. 检查网站是否需要登录（特别是 Bilibili）

### Bilibili 需要登录
- **症状**: "检测到需要登录才能查看完整评论"
- **解决方案**:
  1. 运行 `python script/qr_login.py` 扫码登录
  2. 使用 `--auto-login` 参数

### 识别错误的 CSS 选择器
- **症状**: 特定网站评论提取失败
- **解决方案**:
  1. 使用 `--no-headless` 禁用无头模式
  2. 在浏览器开发者工具中检查评论元素的类名或属性
  3. 使用 `--selector` 手动指定选择器

## 常见问题

**Q: 支持其他平台吗？**
A: 支持。可以参考现有平台的实现，创建新的平台爬虫类并继承 `BaseCollector`。

**Q: 为什么 Bilibili 返回 0 条评论？**
A: Bilibili 有时会根据地区和账户权限限制评论显示。使用 `--auto-login` 登录后通常可以解决。

**Q: 可以同时爬取多个视频吗？**
A: 可以。在脚本中循环调用爬虫，或编写 bash 脚本逐个处理 URL。

**Q: 爬取速度很慢怎么办？**
A:
- 减少 `--max_comments` 和 `--max_replies` 的值
- 减少 `--scroll_times` 的值
- 使用 `--headless` 模式（默认启用）

