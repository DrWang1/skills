#!/usr/bin/env python3
"""把 Markdown 渲染成小红书配图/封面（1080 宽）。

复用 xiaohongshu-skill 的 md_to_images 实现，因此必须用该 skill 的虚拟环境运行：

  uv run --project ~/.agents/skills/xiaohongshu-skill \
      python ~/.agents/skills/xhs-content-studio/scripts/render_cover.py \
      --file <workspace>/note.md --outdir <workspace>/assets --width 1080

输出 JSON：{"status": "ok", "images": [...]}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_XHS_DIR = Path.home() / ".agents" / "skills" / "xiaohongshu-skill"


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown 渲染为小红书配图")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Markdown 文件路径")
    src.add_argument("--text", help="Markdown 文本")
    ap.add_argument("--outdir", required=True, help="图片输出目录")
    ap.add_argument("--width", type=int, default=1080, help="图片宽度（默认 1080）")
    args = ap.parse_args()

    xhs_dir = Path(os.environ.get("XHS_SKILL_DIR", str(DEFAULT_XHS_DIR))).expanduser().resolve()
    if not (xhs_dir / "scripts" / "publish.py").is_file():
        print(json.dumps({"status": "error", "message": f"找不到 xiaohongshu-skill: {xhs_dir}"}, ensure_ascii=False))
        return 1

    sys.path.insert(0, str(xhs_dir))
    from scripts.publish import md_to_images  # type: ignore

    markdown_text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    images = md_to_images(markdown_text, output_dir=str(outdir), width=args.width)
    print(json.dumps({"status": "ok" if images else "error", "images": images}, ensure_ascii=False, indent=2))
    return 0 if images else 1


if __name__ == "__main__":
    sys.exit(main())
