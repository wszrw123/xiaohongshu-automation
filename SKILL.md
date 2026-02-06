# 小红书自动化发布 Skill

## 概述

基于 Playwright 的小红书自动化发布系统，支持：
- 二维码扫码登录 + **持久化免扫码**（Playwright persistent context）
- 自动生成内容 + 图文发布
- 标签智能联想选择
- 重试机制 + 定时调度
- macOS 适配

核心脚本：`xhs_auto.py`

## 前置要求

- Python 3.8+
- Playwright（`pip install playwright && playwright install chromium`）
- schedule（可选，定时调度用：`pip install schedule`）
- Pillow（可选，生成默认封面：`pip install pillow`）

## 快速开始

### 1. 首次登录（扫码一次，永久缓存）

```bash
python3 xhs_auto.py login
```

浏览器窗口打开后，用小红书APP扫描二维码。登录成功后浏览器数据自动保存到 `browser_data/` 目录，后续运行无需再扫码。

### 2. 发布笔记

```bash
# 从JSON文件发布
python3 xhs_auto.py publish --file content/post.json

# 直接指定标题、正文、标签
python3 xhs_auto.py publish --title "标题" --content "正文" --tags "标签1,标签2"

# 指定自定义图片（可选，默认用 content/default_cover.png）
python3 xhs_auto.py publish --title "标题" --content "正文" --images "img1.png,img2.png"

# 试运行（填写内容但不点发布按钮）
python3 xhs_auto.py publish --file content/post.json --dry-run
```

### 3. 定时调度

```bash
python3 xhs_auto.py schedule
```

定时调度需配合外部内容源（JSON文件），在 `auto_manager_config.json` 中配置时间。

## 发布流程

1. 启动浏览器（persistent context，自动恢复登录状态）
2. 检测登录状态（选择器：`.main-container .user .link-wrapper .channel`）
3. 若未登录，显示二维码等待扫码（300秒超时）
4. 导航到 `creator.xiaohongshu.com/publish/publish`
5. 点击「上传图文」TAB
6. 上传封面图片（默认使用 `content/default_cover.png`）
7. 填写标题（选择器：`div.d-input input`，限20字）
8. 填写正文（选择器：`[role="textbox"]`，限1000字）
9. 添加标签（输入 `#` 触发联想，选择 `#creator-editor-topic-container .item`）
10. 点击发布按钮（选择器：`.publish-page-publish-btn button.bg-red`）
11. 截图确认结果

## 内容JSON格式

```json
{
  "title": "笔记标题（不超过20字）",
  "content": "笔记正文（不超过1000字）",
  "tags": ["标签1", "标签2", "标签3"]
}
```

## 目录结构

```
xiaohongshu-automation/
├── xhs_auto.py                # 核心自动化脚本
├── auto_manager_config.json   # 内容策略配置（主题、标签池、发布时间）
├── openclaw_automation_config.json  # OpenClaw 集成配置
├── browser_data/              # 持久化浏览器数据（登录状态缓存）
├── content/                   # 内容文件
│   ├── default_cover.png      # 默认封面图
│   └── post_*.json            # 生成的内容文件
├── screenshots/               # 自动截图
├── logs/                      # 运行日志 + 发布报告
└── SKILL.md                   # 本文件
```

## OpenClaw 集成

在 OpenClaw 中可直接调用以下命令：

| 命令 | 说明 |
|------|------|
| `python3 xhs_auto.py login` | 扫码登录（首次需要） |
| `python3 xhs_auto.py publish --file <json>` | 从JSON文件发布 |
| `python3 xhs_auto.py publish --title <标题> --content <正文> --tags <标签>` | 直接指定内容发布 |
| `python3 xhs_auto.py publish --file <json> --dry-run` | 试运行 |
| `python3 xhs_auto.py schedule` | 启动定时调度 |

## 配置说明

### auto_manager_config.json

```json
{
  "schedule": {
    "daily_posts": 2,
    "post_times": ["08:00", "20:00"],
    "timezone": "Asia/Shanghai"
  },
  "safety": {
    "rate_limiting": true,
    "max_daily_posts": 50
  }
}
```

## 安全提示

- 小红书同一账号不允许多个网页端同时登录，登录 MCP 后不要在其他浏览器登录
- 每日发帖量建议不超过 50 篇
- 遵守小红书平台规则，避免账号封禁
- `browser_data/` 目录包含登录凭据，请妥善保管

## 技术参考

- 选择器和流程参考 [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)
- 使用 Playwright persistent context 实现登录持久化
- 标题限制 20 字，正文限制 1000 字