# YouTube Comment Collector - 最终版本

**版本**: 2.0 (合并版本)  
**日期**: 2026-02-27  
**状态**: ✅ 完成

---

## 功能特性

### 支持两种模式

#### 1. 单个视频模式
爬取单个 YouTube Shorts 视频的评论和统计信息

#### 2. 批量模式
从 YouTube Shorts 首页自动导航，连续爬取多个视频的评论

### 功能列表

- ✅ 单个视频评论爬取
- ✅ 批量视频自动导航爬取（5个视频演示）
- ✅ 视频统计信息提取（点赞、评论数、不喜欢、分享）
- ✅ 评论作者名正确提取
- ✅ 评论内容完整提取
- ✅ 支持评论回复提取（可选）
- ✅ 中文数字单位解析（万、千）
- ✅ 自动导航下一个视频（批量模式）
- ✅ 灵活的参数配置

---

## 使用方法

### 单个视频模式

```bash
# 基本用法
python comment_youtube.py --url "https://www.youtube.com/shorts/VIDEO_ID"

# 自定义输出文件
python comment_youtube.py --url "https://www.youtube.com/shorts/VIDEO_ID" \
  --output my_comments.json

# 提取评论回复
python comment_youtube.py --url "https://www.youtube.com/shorts/VIDEO_ID" \
  --ensure_fedback

# 显示浏览器窗口
python comment_youtube.py --url "https://www.youtube.com/shorts/VIDEO_ID" \
  --no-headless
```

### 批量模式

```bash
# 爬取 5 个视频（默认）
python comment_youtube.py --batch

# 爬取 10 个视频
python comment_youtube.py --batch --count 10 --output my_batch.json

# 显示浏览器窗口
python comment_youtube.py --batch --count 5 --no-headless
```

---

## 命令参数说明

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--url`, `-u` | 视频 URL（单个模式必需） | - |
| `--batch`, `-b` | 启用批量模式 | False |
| `--output`, `-o` | 输出文件路径 | comments.json |
| `--headless` | 使用无头浏览器 | True |
| `--no-headless` | 显示浏览器窗口 | - |

### 单个视频参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--max_comments`, `-m` | 最大爬取评论数 | 100 |
| `--scroll_times`, `-s` | 滚动次数 | 5 |
| `--ensure_fedback` | 提取评论回复 | False |
| `--max_replies` | 每条评论最大回复数 | 100 |

### 批量参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--count`, `-c` | 要爬取的视频数量 | 5 |

---

## 输出格式

### 单个视频输出

```json
{
  "metadata": {
    "url": "https://www.youtube.com/shorts/VIDEO_ID",
    "collected_at": "2026-02-27T14:00:00",
    "total_count": 20,
    "platform": "youtube",
    "video_stats": {
      "likes": 13,
      "dislikes": 0,
      "comments": 77,
      "shares": 0
    }
  },
  "comments": [
    {
      "author": "@username",
      "content": "评论内容",
      "time": "发布时间",
      "likes": 0,
      "index": 1
    }
  ]
}
```

### 批量输出

```json
{
  "metadata": {
    "collected_at": "2026-02-27T14:00:00",
    "total_videos": 5,
    "platform": "youtube_shorts",
    "total_comments": 42
  },
  "videos": [
    {
      "index": 1,
      "url": "https://www.youtube.com/shorts/VIDEO_ID",
      "video_stats": {...},
      "total_comments_collected": 20,
      "comments": [...]
    }
  ]
}
```

---

## 技术架构

### 脚本结构

```
comment_youtube.py (32 KB, 875 行)
├── YoutubeCollector 类
│   ├── 单个视频爬取方法
│   │   ├── _wait_for_comments()
│   │   ├── _scroll_to_load()
│   │   ├── _extract_comment()
│   │   └── _extract_video_stats()
│   │
│   ├── 批量爬取方法
│   │   ├── collect_batch()
│   │   ├── _collect_single_video()
│   │   ├── _navigate_to_next_video()
│   │   └── _save_batch_data()
│   │
│   └── 工具方法
│       ├── _parse_count()
│       ├── save()
│       └── _extract_comment_replies()
│
└── main() 函数
    └── 参数解析和执行
```

### 关键算法

1. **评论去重**: 使用 (作者名 + 评论内容) 作为唯一标识
2. **数字解析**: 支持中文单位（万、千）的自动转换
3. **自动导航**: 通过键盘事件 (↓) 自动切换视频
4. **增量滚动**: 小幅度滚动 (+300px) 确保不漏评论

---

## 限制说明

### YouTube 未登录限制

- **评论数限制**: 未登录用户每个视频只能显示 ~20 条评论
- **实际评论数**: 视频可能有 50-700+ 条，但无法全部显示
- **这不是爬虫问题**: 这是 YouTube 的服务器端限制

### 解决方案

要获取更多评论，可以：

1. 使用已登录的账户（需添加 Cookie）
2. 多次访问同一视频以增加样本量
3. 结合登录和增量爬取获取完整评论

---

## 完整使用示例

### 示例 1: 爬取单个视频

```bash
cd /path/to/script
python comment_youtube.py \
  --url "https://www.youtube.com/shorts/hR8h71elE8Y" \
  --output "video_comments.json" \
  --max_comments 200 \
  --scroll_times 10
```

### 示例 2: 批量爬取 5 个视频

```bash
python comment_youtube.py \
  --batch \
  --count 5 \
  --output "batch_results.json"
```

### 示例 3: 观看浏览器动作

```bash
python comment_youtube.py \
  --url "https://www.youtube.com/shorts/abc123" \
  --no-headless \
  --ensure_fedback
```

---

## 测试结果

### 单个视频测试
- **URL**: https://www.youtube.com/shorts/hR8h71elE8Y
- **爬取评论**: 20 条
- **视频评论**: 77 条（未登录限制）
- **点赞数**: 13
- **执行时间**: ~3 分钟

### 批量测试 (5个视频)
- **总视频数**: 5
- **总评论数**: 42 条
- **平均每视频**: 8.4 条
- **执行时间**: ~10 分钟

---

## 文件清理记录

✅ 已删除：
- `youtube_shorts_batch.py` (独立脚本)
- `BATCH_COLLECTION_SUMMARY.md` (独立文档)

✅ 保留：
- `comment_youtube.py` (统一脚本，875行)
- `youtube_hR8h71elE8Y.json` (测试数据)
- `youtube_shorts_batch.json` (批量测试数据)

---

## 项目规范

### YouTube 脚本规则

✅ **规范遵守**:
- [x] 每个平台只有一个爬虫脚本
- [x] YouTube 只有 `comment_youtube.py`
- [x] 单个脚本支持所有功能（单个 + 批量）
- [x] 清晰的代码结构
- [x] 完整的参数支持

---

## 后续改进建议

1. 🔐 **Cookie 认证** - 支持登录账户获取完整评论
2. 💾 **数据库支持** - 改为存储到数据库而非 JSON
3. 📊 **数据分析** - 添加评论情感分析、热词提取
4. 🔄 **增量更新** - 支持增量爬取新评论
5. 🌐 **多语言** - 改进多语言评论处理

---

## 状态

- ✅ 脚本合并完成
- ✅ 功能测试通过
- ✅ 文档编写完成
- ✅ 项目规范遵守

**可用性**: 生产环境就绪 ✅

---

**最后更新**: 2026-02-27  
**版本**: 2.0  
**作者**: Claude Code
