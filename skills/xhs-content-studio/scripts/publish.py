#!/usr/bin/env python3
"""发布小红书笔记的确认门封装。

设计原则：默认**不触碰浏览器**。只有显式传入 --confirm 才会真正发布，
并且一定会带 --auto-publish。未确认时只回显将要发布的内容。

用法：
  # 1) 预览（不发布）
  python3 publish.py --title "标题" --content "正文" --images a.jpg,b.jpg --tags "标签1,标签2"
  # 2) 用户确认后发布
  python3 publish.py --title "标题" --content "正文" --images a.jpg,b.jpg --tags "标签1,标签2" --confirm
  # 3) Markdown 渲染发布
  python3 publish.py --mode md --title "标题" --file note.md --confirm
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_XHS_DIR = Path.home() / ".agents" / "skills" / "xiaohongshu-skill"

SUCCESS = "confirmed"
PENDING = "ready"


def parse_json_output(stdout: str) -> dict:
    stdout = stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        pass
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    match = re.search(r"\{.*\}", stdout, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {"status": "unknown", "raw": stdout}


def main() -> int:
    ap = argparse.ArgumentParser(description="小红书发布确认门")
    ap.add_argument("--mode", choices=["image", "md", "longform"], default="image")
    ap.add_argument("--title", required=True)
    ap.add_argument("--content", help="正文（image / longform 必填）")
    ap.add_argument("--file", help="Markdown 文件（md 模式必填）")
    ap.add_argument("--images", help="图片路径，逗号分隔（image 模式必填）")
    ap.add_argument("--tags", help="话题标签，逗号分隔")
    ap.add_argument("--profile", help="账号 profile")
    ap.add_argument("--schedule-time", help="定时发布，格式 '2025-01-01 12:00'")
    ap.add_argument("--headless", default="true", help="true / false（默认 true）")
    ap.add_argument("--confirm", action="store_true", help="用户已确认，执行真实发布")
    args = ap.parse_args()

    if args.mode == "image" and not args.images:
        ap.error("image 模式需要 --images")
    if args.mode == "image" and not args.content:
        ap.error("image 模式需要 --content")
    if args.mode == "md" and not args.file:
        ap.error("md 模式需要 --file")

    if not args.confirm:
        preview = {
            "status": "awaiting_confirmation",
            "message": "尚未发布。请向用户展示以下内容并等待明确确认，再追加 --confirm 执行。",
            "mode": args.mode,
            "title": args.title,
            "content": args.content,
            "file": args.file,
            "images": args.images,
            "tags": args.tags,
            "profile": args.profile,
            "schedule_time": args.schedule_time,
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    xhs_dir = Path(os.environ.get("XHS_SKILL_DIR", str(DEFAULT_XHS_DIR))).expanduser().resolve()
    if not (xhs_dir / "scripts" / "__main__.py").is_file():
        print(json.dumps({"status": "error", "message": f"找不到 xiaohongshu-skill: {xhs_dir}"}, ensure_ascii=False))
        return 1

    cmd = ["uv", "run", "python", "-m", "scripts"]
    if args.profile:
        cmd += ["--profile", args.profile]

    if args.mode == "image":
        cmd += ["publish", "--title", args.title, "--content", args.content, "--images", args.images]
    elif args.mode == "longform":
        cmd += ["publish-longform", "--title", args.title, "--content", args.content]
    else:
        cmd += ["publish-md", "--title", args.title, "--file", args.file]
        if args.content:
            cmd += ["--content", args.content]

    if args.tags:
        cmd += ["--tags", args.tags]
    if args.schedule_time:
        cmd += ["--schedule-time", args.schedule_time]
    cmd += ["--headless", args.headless, "--auto-publish"]

    proc = subprocess.run(cmd, cwd=str(xhs_dir), capture_output=True, text=True)
    result = parse_json_output(proc.stdout)
    status = result.get("status")

    if status == SUCCESS:
        result["action"] = "已确认发布成功"
    elif status == PENDING:
        result["action"] = "已提交但未确认，请人工到小红书 App/网页复核，禁止自动重试"
    elif status in {"submitted_unconfirmed", "failed", "error", "captcha_required"}:
        result["action"] = "未成功，停止自动操作并转人工处理"
    else:
        result.setdefault("action", "结果未知，请人工复核")

    result["exit_code"] = proc.returncode
    if proc.stderr.strip():
        result["stderr_tail"] = proc.stderr.strip().splitlines()[-5:]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
