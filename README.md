# Xiaohongshu Automation Skill 📕

> 基于 Playwright 的小红书自动化发布系统，支持 OpenClaw 集成

一个功能完整的小红书自动化发布工具，支持二维码扫码登录、持久化会话、定时发布、内容管理等功能。专为 OpenClaw AI 助手设计，可实现完全自动化的小红书内容运营。

## ✨ 核心特性

- 🔐 **持久化登录** - 扫码一次，永久免扫码（Playwright persistent context）
- 🤖 **完全自动化** - 从内容准备到发布完成，无需人工干预
- ⏰ **定时调度** - 支持定时发布，自动化内容运营
- 🎯 **智能标签** - 自动联想和选择相关标签
- 📸 **截图记录** - 完整的发布过程截图，便于调试和验证
- 🔧 **多重方案** - Python/JavaScript/OpenClaw 集成多种发布方式
- 📊 **日志报告** - 详细的发布日志和统计数据
- 💾 **会话恢复** - 登录状态持久化，随时恢复使用

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Playwright
- Pillow（可选，用于生成默认封面）
- macOS/Linux/Windows

### 安装依赖

```bash
# 安装 Python 依赖
pip install playwright schedule pillow

# 安装 Playwright 浏览器
playwright install chromium
```

### 首次登录（扫码一次，永久缓存）

```bash
python3 xhs_auto.py login
```

浏览器窗口打开后，用小红书APP扫描二维码。登录成功后浏览器数据自动保存到 `browser_data/` 目录，后续运行无需再扫码。

### 发布笔记

```bash
# 从 JSON 文件发布
python3 xhs_auto.py publish --file content/post.json

# 直接指定内容发布
python3 xhs_auto.py publish \
  --title "笔记标题" \
  --content "笔记正文" \
  --tags "标签1,标签2,标签3"

# 指定自定义图片（可选，默认使用 content/default_cover.png）
python3 xhs_auto.py publish \
  --title "标题" \
  --content "正文" \
  --images "img1.png,img2.png,img3.png"

# 试运行（填写内容但不点击发布按钮）
python3 xhs_auto.py publish --file content/post.json --dry-run
```

### 定时调度

```bash
python3 xhs_auto.py schedule
```

定时调度需配合外部内容源（JSON 文件），在 `auto_manager_config.json` 中配置发布时间。

## 📖 详细使用指南

### 发布流程

1. **启动浏览器** - 使用 persistent context，自动恢复登录状态
2. **检测登录状态** - 检查是否已登录（选择器：`.main-container .user .link-wrapper .channel`）
3. **扫码登录** - 若未登录，显示二维码等待扫码（300秒超时）
4. **导航到发布页** - 跳转到 `creator.xiaohongshu.com/publish/publish`
5. **上传图文** - 点击「上传图文」TAB
6. **上传封面** - 上传封面图片（默认 `content/default_cover.png`）
7. **填写标题** - 填写笔记标题（限20字）
8. **填写正文** - 填写笔记正文（限1000字）
9. **添加标签** - 输入 `#` 触发联想，选择相关标签
10. **点击发布** - 点击发布按钮
11. **截图确认** - 截图保存发布结果

### 内容 JSON 格式

```json
{
  "title": "笔记标题（不超过20字）",
  "content": "笔记正文（不超过1000字）",
  "tags": ["标签1", "标签2", "标签3"]
}
```

### 配置文件

#### auto_manager_config.json

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

## 🛠️ OpenClaw 集成

本技能专为 OpenClaw AI 助手设计，可直接在 OpenClaw 中调用：

| 命令 | 说明 |
|------|------|
| `python3 xhs_auto.py login` | 扫码登录（首次需要） |
| `python3 xhs_auto.py publish --file <json>` | 从 JSON 文件发布 |
| `python3 xhs_auto.py publish --title <标题> --content <正文> --tags <标签>` | 直接指定内容发布 |
| `python3 xhs_auto.py publish --file <json> --dry-run` | 试运行 |
| `python3 xhs_auto.py schedule` | 启动定时调度 |

### 与内容生成技能配合

推荐配合 `redbook-content-generator` 技能使用，实现完整的自动化流程：

1. **内容生成** - 使用 `redbook-content-generator` 生成小红书风格内容
2. **图片渲染** - 将 Markdown 内容渲染为精美图片卡片
3. **自动发布** - 使用本技能将内容发布到小红书

## 📁 项目结构

```
xiaohongshu-automation/
├── xhs_auto.py                      # 核心自动化脚本
├── auto_manager_config.json         # 自动化管理配置
├── openclaw_automation_config.json  # OpenClaw 集成配置
├── browser_data/                    # 持久化浏览器数据（登录状态）
├── content/                         # 内容文件目录
│   ├── default_cover.png            # 默认封面图
│   └── post_*.json                  # 生成的内容文件
├── screenshots/                     # 发布过程截图
├── logs/                            # 运行日志 + 发布报告
│   ├── xhs_auto_YYYYMMDD.log       # 每日运行日志
│   └── report_YYYYMMDD_HHMMSS.json # 发布报告
├── SKILL.md                         # OpenClaw 技能文档
└── README.md                        # 本文件
```

## 🔧 高级功能

### 多重发布方案

本项目提供多种自动化发布方式，适应不同场景：

#### 1. Python Playwright 自动化（推荐）
```bash
python3 auto_publish_simple.py
```
- 全流程浏览器控制
- 持久化登录状态
- 完整的错误处理和重试机制

#### 2. JavaScript Console 自动化
```bash
# 在已登录的小红书页面控制台执行
node browser_automation_script.js
```
- 直接在浏览器执行
- 快速简单
- 适合调试和测试

#### 3. OpenClaw 集成方案
```bash
python3 auto_with_openclaw.py
```
- 与 OpenClaw 深度集成
- 支持消息触发
- 完整的日志记录

### 监控和调试

#### 实时监控
```bash
# 实时监控自动化过程
./realtime_monitor.sh
```

#### 查看发布报告
```bash
# 查看最新发布报告
cat logs/report_$(ls -t logs/report_*.json | head -1)
```

#### 检查自动化状态
```bash
python3 check_auto_status.py
```

## ⚠️ 安全提示

- **多设备登录限制** - 小红书同一账号不允许多个网页端同时登录，使用本工具后不要在其他浏览器登录
- **每日发帖量** - 建议每日发帖量不超过 50 篇，避免账号风险
- **平台规则** - 遵守小红书平台规则，避免账号封禁
- **数据安全** - `browser_data/` 目录包含登录凭据，请妥善保管
- **辅助功能** - macOS 用户需要在系统设置中授予终端辅助功能权限

## 🐛 故障排除

### 登录问题

```bash
# 1. 清除浏览器数据，重新登录
rm -rf browser_data/
python3 xhs_auto.py login

# 2. 检查网络连接
ping creator.xiaohongshu.com

# 3. 查看详细日志
tail -f logs/xhs_auto_$(date +%Y%m%d).log
```

### 发布失败

```bash
# 1. 检查图片格式和大小（支持 JPG、PNG，建议 3:4 比例）
file content/default_cover.png

# 2. 验证内容格式（标题限20字，正文限1000字）
python3 -c "
import json
with open('content/post.json') as f:
    data = json.load(f)
    print(f'标题长度: {len(data[\"title\"])}')
    print(f'正文长度: {len(data[\"content\"])}')
"

# 3. 试运行，不实际发布
python3 xhs_auto.py publish --file content/post.json --dry-run
```

### 浏览器自动化问题

```bash
# 1. 重新安装 Playwright
playwright install chromium

# 2. 检查 Playwright 版本
playwright --version

# 3. 测试浏览器启动
python3 test_playwright.py
```

## 📊 日志和报告

### 日志格式

```
2026-02-06 21:48:07,307 [INFO] --- 第 1/3 次尝试 ---
2026-02-06 21:48:07,307 [INFO] 开始发布: 2026公考冲刺必看！最新资讯全掌握
2026-02-06 21:48:12,605 [INFO] 已点击上传图文 TAB
2026-02-06 21:48:20,585 [INFO] 标题已填写 (选择器: div.d-input input)
2026-02-06 21:48:42,292 [INFO] 已添加 6 个标签
2026-02-06 21:48:50,025 [INFO] 发布成功！
```

### 发布报告格式

```json
{
  "time": "2026-02-06T21:48:51.327475",
  "title": "笔记标题",
  "tags": ["标签1", "标签2"],
  "result": {
    "success": true,
    "status": "success"
  }
}
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## ⚡ 相关项目

- [redbook-content-generator](https://github.com/wszrw123/redbook-content-generator) - 小红书笔记内容生成 + 图片卡片渲染
- [qq-auto-reply](https://github.com/wszrw123/qq-auto-reply) - QQ 桌面端自动回复技能

## ⚠️ 免责声明

本工具仅供学习和研究使用，请遵守相关法律法规和小红书平台规则。使用本工具产生的任何问题，作者不承担相关责任。

---

**Made with ❤️ for OpenClaw Community**
