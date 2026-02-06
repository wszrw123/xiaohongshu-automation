#!/usr/bin/env python3
"""
小红书自动化发布系统 v2.0 (统一优化版)
- Cookie持久化登录（免扫码）
- 内容生成 + 自动发布
- 重试机制 + 定时调度
- 适配macOS + 正确的选择器
"""

import asyncio
import json
import os
import sys
import time
import random
import argparse
import logging
from datetime import datetime
from pathlib import Path

# ============================================================
# 配置
# ============================================================

BASE_DIR = Path(__file__).parent.resolve()
USER_DATA_DIR = BASE_DIR / "browser_data"  # 持久化浏览器数据目录
CONTENT_DIR = BASE_DIR / "content"
LOGS_DIR = BASE_DIR / "logs"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
CONFIG_FILE = BASE_DIR / "auto_manager_config.json"

# 小红书URL
XHS_EXPLORE = "https://www.xiaohongshu.com/explore"
XHS_CREATOR = "https://creator.xiaohongshu.com"
XHS_PUBLISH = "https://creator.xiaohongshu.com/publish/publish?source=official"
DEFAULT_COVER = BASE_DIR / "content" / "default_cover.png"

# 登录检测选择器（来自 xiaohongshu-mcp 项目验证）
LOGIN_CHECK_SELECTOR = ".main-container .user .link-wrapper .channel"
QR_IMG_SELECTOR = ".login-container .qrcode-img"

# 浏览器配置
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--window-size=1280,900",
    "--no-first-run",
    "--no-default-browser-check",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

# ============================================================
# 日志
# ============================================================

LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            LOGS_DIR / f"xhs_auto_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("xhs_auto")

# ============================================================
# 内容生成器
# ============================================================

class ContentGenerator:
    """内容加载/保存工具（不含内建模板，内容由调用方提供）"""

    def load_from_file(self, filepath: str) -> dict:
        """从JSON文件加载内容"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "title": data.get("title", ""),
            "content": data.get("content", data.get("body", "")),
            "tags": data.get("tags", []),
        }

    def save(self, content: dict) -> Path:
        """保存内容到JSON文件"""
        CONTENT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = CONTENT_DIR / f"post_{ts}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        log.info(f"内容已保存: {filepath}")
        return filepath


# ============================================================
# 核心自动化引擎
# ============================================================

class XHSAutomation:
    """小红书自动化发布引擎（Playwright persistent context）"""

    def __init__(self, headless=False):
        self.headless = headless
        self.playwright = None
        self.context = None  # persistent context 同时是 browser context
        self.page = None

    # ---------- 生命周期 ----------

    async def start(self):
        """启动浏览器（使用持久化上下文，自动缓存登录状态）"""
        from playwright.async_api import async_playwright

        USER_DATA_DIR.mkdir(exist_ok=True)

        self.playwright = await async_playwright().start()
        # launch_persistent_context 会把 cookies、localStorage、sessionStorage
        # 等所有浏览器数据持久化到 user_data_dir
        # 登录一次后后续不需要再次扫码
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            args=BROWSER_ARGS,
        )

        # 使用现有页面或创建新页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        log.info("浏览器已启动 (持久化模式)")

    async def stop(self):
        """关闭浏览器（数据自动保存到 user_data_dir）"""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        log.info("浏览器已关闭（登录状态已持久化）")

    # ---------- 登录 ----------

    async def check_login(self) -> bool:
        """
        检查是否已登录
        使用 xiaohongshu-mcp 项目验证过的选择器:
        .main-container .user .link-wrapper .channel
        """
        try:
            await self.page.goto(XHS_EXPLORE, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_timeout(2000)

            # 检测已登录用户的侧边栏元素
            try:
                el = await self.page.wait_for_selector(LOGIN_CHECK_SELECTOR, timeout=5000)
                if el:
                    log.info("检测到已登录状态")
                    return True
            except:
                pass

            log.info("未检测到登录状态")
            return False
        except Exception as e:
            log.warning(f"登录检查异常: {e}")
            return False

    async def login_with_qr(self, timeout=300) -> bool:
        """二维码登录"""
        log.info("打开小红书页面...")
        await self.page.goto(XHS_EXPLORE, wait_until="domcontentloaded", timeout=20000)
        await self.page.wait_for_timeout(2000)

        # 检查是否已登录
        try:
            el = await self.page.wait_for_selector(LOGIN_CHECK_SELECTOR, timeout=3000)
            if el:
                log.info("已登录，无需扫码")
                return True
        except:
            pass

        # 截图当前页面
        await self._screenshot("login_page")
        log.info(f"请在浏览器窗口中扫描二维码登录（{timeout}秒超时）")
        log.info("提示：打开小红书APP > 扫一扫 > 扫描屏幕上的二维码")

        # 等待登录成功 — 检测 .main-container .user .link-wrapper .channel 出现
        for i in range(timeout):
            try:
                el = await self.page.wait_for_selector(LOGIN_CHECK_SELECTOR, timeout=800)
                if el:
                    log.info("检测到登录成功！")
                    return True
            except:
                pass

            if i % 15 == 0:
                log.info(f"等待扫码登录... {i}/{timeout}秒")

            await self.page.wait_for_timeout(200)  # 快速轮询

        log.warning("登录超时")
        return False

    async def ensure_login(self) -> bool:
        """确保已登录（persistent context 自动缓存登录状态）"""
        if await self.check_login():
            return True

        log.info("未登录，开始扫码登录流程")
        return await self.login_with_qr()

    # ---------- 发布 ----------

    async def publish(self, content: dict, dry_run=False, image_paths: list = None) -> dict:
        """
        发布一篇笔记（使用 creator.xiaohongshu.com 发布页）
        content: {"title": str, "content": str, "tags": list}
        image_paths: 图片文件路径列表，为None时使用默认封面
        dry_run: True则只填写不点发布
        """
        result = {"success": False, "status": "init", "time": datetime.now().isoformat()}
        title = content.get("title", "")
        body = content.get("content", "")
        tags = content.get("tags", [])

        # 小红书标题限制 20 字
        if len(title) > 20:
            log.warning(f"标题超过20字，截断: {title[:20]}...")
            title = title[:20]

        # 小红书正文限制 1000 字
        if len(body) > 1000:
            log.warning(f"正文超过1000字，截断")
            body = body[:1000]

        log.info(f"开始发布: {title}")

        try:
            # 1. 导航到创作者发布页
            log.info("导航到发布页面...")
            await self.page.goto(XHS_PUBLISH, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # 检查是否被重定向到登录页
            if "login" in self.page.url or "passport" in self.page.url:
                log.error("未登录，无法发布")
                result["status"] = "not_logged_in"
                return result

            await self._screenshot("publish_page")

            # 2. 等待发布页加载，切换到"上传图文"
            log.info("等待发布页加载...")
            await self.page.wait_for_timeout(2000)

            # 移除可能的弹窗遮罩（xiaohongshu-mcp 的 removePopCover）
            try:
                await self.page.evaluate('document.querySelector("div.d-popover")?.remove()')
            except:
                pass

            # 点击"上传图文" tab — 使用 JS 点击避免 viewport 问题
            tab_clicked = False
            try:
                tab_clicked = await self.page.evaluate('''
                    () => {
                        const allEls = document.querySelectorAll('span, div, a, li');
                        for (const el of allEls) {
                            if (el.textContent.trim() === '上传图文' && el.offsetParent !== null) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }
                ''')
                if tab_clicked:
                    log.info("已点击上传图文 TAB")
            except Exception as e:
                log.info(f"点击图文TAB: {e}")

            if not tab_clicked:
                log.warning("未找到上传图文TAB，尝试继续")

            await self.page.wait_for_timeout(2000)
            await self._screenshot("after_tab_click")

            # 3. 上传图片（必须先上传图片，标题/正文输入框才会出现）
            log.info("上传图片...")
            if not image_paths:
                if DEFAULT_COVER.exists():
                    image_paths = [str(DEFAULT_COVER)]
                else:
                    log.error("没有可用的图片，无法发布")
                    result["status"] = "no_image"
                    return result

            try:
                # file input 通常是 hidden 的，用 state='attached' 而非默认的 'visible'
                upload_input = await self.page.wait_for_selector(
                    '.upload-input, input[type="file"]', timeout=5000, state='attached'
                )
                await upload_input.set_input_files(image_paths)
                log.info(f"已上传 {len(image_paths)} 张图片")
            except Exception as e:
                log.error(f"上传图片失败: {e}")
                result["status"] = "upload_failed"
                return result

            # 等待图片上传完成（检测预览图出现）
            log.info("等待图片上传完成...")
            for wait_i in range(30):
                try:
                    previews = await self.page.query_selector_all('.img-preview-area .pr, .image-item, [class*="preview"] img')
                    if len(previews) >= len(image_paths):
                        log.info(f"图片上传完成，检测到 {len(previews)} 张")
                        break
                except:
                    pass
                await self.page.wait_for_timeout(1000)
            else:
                log.warning("图片上传超时，尝试继续")

            await self.page.wait_for_timeout(2000)
            await self._screenshot("after_upload")

            # 4. 填写标题 (selector: div.d-input input)
            log.info("填写标题...")
            title_filled = False
            for sel in [
                'div.d-input input',
                'div.title-container input',
                'input[placeholder*="标题"]',
                '#title-input',
            ]:
                try:
                    title_el = await self.page.wait_for_selector(sel, timeout=5000)
                    await title_el.click()
                    await title_el.fill(title)
                    title_filled = True
                    log.info(f"标题已填写 (选择器: {sel})")
                    break
                except:
                    continue

            if not title_filled:
                log.warning("未找到标题输入框")

            await self.page.wait_for_timeout(500)

            # 4. 填写正文 (selector: div.ql-editor 或 [role="textbox"])
            log.info("填写正文...")
            body_filled = False
            for sel in [
                'div.ql-editor',
                '[role="textbox"]',
                'div[contenteditable="true"]',
            ]:
                try:
                    body_el = await self.page.wait_for_selector(sel, timeout=5000)
                    await body_el.click()
                    # 使用 fill 或 type 输入内容
                    try:
                        await body_el.fill(body)
                    except:
                        # contenteditable 不支持 fill，用键盘输入
                        await self.page.keyboard.press("Meta+A")
                        await self.page.keyboard.press("Backspace")
                        await self.page.wait_for_timeout(200)
                        for line in body.split("\n"):
                            await self.page.keyboard.type(line, delay=15)
                            await self.page.keyboard.press("Enter")
                            await self.page.wait_for_timeout(50)
                    body_filled = True
                    log.info(f"正文已填写 (选择器: {sel})")
                    break
                except:
                    continue

            if not body_filled:
                log.warning("未找到正文输入区域")

            # 5. 添加标签
            if tags and body_filled:
                log.info(f"添加标签: {tags}")
                await self._add_tags(tags)

            await self.page.wait_for_timeout(1000)
            await self._screenshot("content_filled")

            # 6. 点击发布
            if dry_run:
                log.info("[DRY RUN] 跳过点击发布按钮")
                result["status"] = "dry_run"
                result["success"] = True
                return result

            log.info("点击发布按钮...")
            published = False
            for sel in [
                '.publish-page-publish-btn button.bg-red',
                'button.publishBtn',
                'button[class*="publish"]:not([disabled])',
                'button:has-text("发布")',
            ]:
                try:
                    pub_btn = await self.page.wait_for_selector(sel, timeout=5000)
                    is_disabled = await pub_btn.get_attribute("disabled")
                    if is_disabled:
                        continue
                    await self._screenshot("before_publish")
                    await pub_btn.click()
                    published = True
                    log.info(f"已点击发布按钮 (选择器: {sel})")
                    break
                except:
                    continue

            if not published:
                log.error("未找到可点击的发布按钮")
                await self._screenshot("publish_btn_not_found")
                result["status"] = "publish_btn_not_found"
                return result

            # 7. 等待并检查结果
            await self.page.wait_for_timeout(5000)
            await self._screenshot("after_publish")

            # 检查是否发布成功
            page_text = await self.page.inner_text("body")
            if any(kw in page_text for kw in ["发布成功", "笔记已发布", "已发布"]):
                log.info("发布成功！")
                result["status"] = "success"
                result["success"] = True
            elif "publish" not in self.page.url:
                log.info("页面已跳转，可能发布成功")
                result["status"] = "possible_success"
                result["success"] = True
            else:
                log.warning("未检测到明确的成功提示")
                result["status"] = "uncertain"

        except Exception as e:
            log.error(f"发布过程出错: {e}")
            await self._screenshot("publish_error")
            result["status"] = "error"
            result["error"] = str(e)

        return result

    async def _add_tags(self, tags: list):
        """添加标签（xiaohongshu-mcp 方式：在编辑器中输入 # 然后选择联想）"""
        try:
            # 找到内容编辑器
            editor = None
            for sel in ['div.ql-editor', '[role="textbox"]', 'div[contenteditable="true"]']:
                try:
                    editor = await self.page.wait_for_selector(sel, timeout=2000)
                    if editor:
                        break
                except:
                    continue

            if not editor:
                log.warning("未找到编辑器，无法添加标签")
                return

            await editor.click()
            # 先按多次下箭头到末尾
            for _ in range(20):
                await self.page.keyboard.press("ArrowDown")
            await self.page.keyboard.press("Enter")
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(500)

            for tag in tags[:10]:
                tag = tag.lstrip("#")
                # 输入 # 然后输入标签文字
                await self.page.keyboard.type("#", delay=100)
                await self.page.wait_for_timeout(200)
                for char in tag:
                    await self.page.keyboard.type(char, delay=50)
                    await self.page.wait_for_timeout(50)
                await self.page.wait_for_timeout(1000)

                # 尝试点击标签联想下拉框的第一个选项
                try:
                    topic_item = await self.page.wait_for_selector(
                        '#creator-editor-topic-container .item', timeout=2000
                    )
                    if topic_item:
                        await topic_item.click()
                        log.info(f"已选择标签联想: {tag}")
                    else:
                        await self.page.keyboard.type(" ")
                except:
                    # 没有联想，输入空格结束
                    await self.page.keyboard.type(" ")

                await self.page.wait_for_timeout(500)

            log.info(f"已添加 {min(10, len(tags))} 个标签")
        except Exception as e:
            log.warning(f"添加标签失败: {e}")

    # ---------- 工具方法 ----------

    async def _screenshot(self, name: str):
        """截图"""
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        path = SCREENSHOTS_DIR / f"{name}_{ts}.png"
        try:
            await self.page.screenshot(path=str(path))
            log.info(f"截图: {path.name}")
        except Exception as e:
            log.warning(f"截图失败: {e}")


# ============================================================
# 带重试的发布
# ============================================================

async def publish_with_retry(content: dict, headless=False, dry_run=False, image_paths: list = None) -> dict:
    """带重试机制的发布（复用同一个 persistent context）"""
    bot = XHSAutomation(headless=headless)
    try:
        await bot.start()

        if not await bot.ensure_login():
            log.error("登录失败，中止发布")
            return {"success": False, "status": "login_failed"}

        for attempt in range(1, MAX_RETRIES + 1):
            log.info(f"--- 第 {attempt}/{MAX_RETRIES} 次尝试 ---")
            try:
                result = await bot.publish(content, dry_run=dry_run, image_paths=image_paths)
                if result["success"]:
                    return result
                log.warning(f"发布未确认成功 (status={result['status']}), 将重试...")
            except Exception as e:
                log.error(f"第 {attempt} 次尝试异常: {e}")

            if attempt < MAX_RETRIES:
                log.info(f"等待 {RETRY_DELAY} 秒后重试...")
                await asyncio.sleep(RETRY_DELAY)

        return {"success": False, "status": "max_retries_exceeded"}
    finally:
        await bot.stop()


# ============================================================
# 定时调度
# ============================================================

def run_scheduler():
    """定时调度发布任务"""
    import schedule as sched

    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

    post_times = config.get("content_strategy", {}).get("post_times", ["08:00", "20:00"])
    gen = ContentGenerator()

    def scheduled_publish():
        log.info("定时任务触发：开始生成并发布内容")
        content = gen.generate()
        gen.save(content)
        result = asyncio.run(publish_with_retry(content))
        log.info(f"定时发布结果: {result}")
        _save_report(content, result)

    for t in post_times:
        sched.every().day.at(t).do(scheduled_publish)
        log.info(f"已设置定时发布: 每日 {t}")

    log.info(f"调度器已启动，共 {len(post_times)} 个定时任务")
    log.info("按 Ctrl+C 停止")

    try:
        while True:
            sched.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("调度器已停止")


# ============================================================
# 报告
# ============================================================

def _save_report(content: dict, result: dict):
    """保存发布报告"""
    LOGS_DIR.mkdir(exist_ok=True)
    report = {
        "time": datetime.now().isoformat(),
        "title": content.get("title", ""),
        "tags": content.get("tags", []),
        "result": result,
    }
    report_file = LOGS_DIR / f"report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.info(f"报告已保存: {report_file}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="小红书自动化发布系统 v2.0")
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # publish 命令
    p_pub = sub.add_parser("publish", help="发布一篇笔记")
    p_pub.add_argument("--file", help="内容JSON文件路径")
    p_pub.add_argument("--title", help="笔记标题（不指定file时使用）")
    p_pub.add_argument("--content", help="笔记正文（不指定file时使用）")
    p_pub.add_argument("--tags", help="标签，逗号分隔")
    p_pub.add_argument("--images", help="图片路径，逗号分隔（可选，默认用default_cover）")
    p_pub.add_argument("--dry-run", action="store_true", help="试运行（不点发布按钮）")
    p_pub.add_argument("--headless", action="store_true", help="无头模式")

    # schedule 命令
    p_sched = sub.add_parser("schedule", help="启动定时调度")

    # login 命令
    p_login = sub.add_parser("login", help="扫码登录并保存Cookie")

    # generate 命令（已废弃，保留入口给出提示）
    p_gen = sub.add_parser("generate", help="[已废弃] 请直接用 --file 或 --title 发布")

    args = parser.parse_args()

    if args.command == "publish":
        gen = ContentGenerator()

        # 确定内容来源
        if args.file:
            content = gen.load_from_file(args.file)
        elif args.title:
            content = {
                "title": args.title,
                "content": args.content or "",
                "tags": args.tags.split(",") if args.tags else [],
            }
        else:
            log.error("请指定内容来源: --file <json文件> 或 --title <标题> --content <正文> --tags <标签>")
            sys.exit(1)

        # 图片参数
        img_paths = None
        if hasattr(args, 'images') and args.images:
            img_paths = [p.strip() for p in args.images.split(",")]

        log.info(f"准备发布: {content['title']}")
        result = asyncio.run(
            publish_with_retry(content, headless=args.headless, dry_run=args.dry_run, image_paths=img_paths)
        )
        _save_report(content, result)

        if result["success"]:
            log.info("发布成功！请在小红书APP中验证。")
        else:
            log.error(f"发布失败: {result.get('status')}")
            sys.exit(1)

    elif args.command == "schedule":
        run_scheduler()

    elif args.command == "login":
        async def do_login():
            bot = XHSAutomation(headless=False)
            await bot.start()
            ok = await bot.ensure_login()
            await bot.stop()
            return ok

        ok = asyncio.run(do_login())
        if ok:
            log.info(f"登录成功！浏览器数据已保存到 {USER_DATA_DIR}")
        else:
            log.error("登录失败")
            sys.exit(1)

    elif args.command == "generate":
        log.info("generate 命令已移除内置模板。请直接使用 --file 或 --title/--content/--tags 发布。")
        log.info("示例: python3 xhs_auto.py publish --title '标题' --content '正文' --tags '标签1,标签2'")

    else:
        parser.print_help()
        print("\n快速开始:")
        print("  python3 xhs_auto.py login          # 首次扫码登录")
        print("  python3 xhs_auto.py publish --file content/post.json      # 从文件发布")
        print("  python3 xhs_auto.py publish --title '标题' --content '正文' --tags '标签1,标签2'")
        print("  python3 xhs_auto.py publish --file post.json --dry-run    # 试运行")
        print("  python3 xhs_auto.py schedule                              # 启动定时调度")


if __name__ == "__main__":
    main()
