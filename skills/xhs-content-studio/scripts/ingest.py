#!/usr/bin/env python3
"""汇总用户发来的素材（图片 / 链接 / 文字）到一个工作区。

只使用标准库。产出：
  <workspace>/materials.json   结构化素材
  <workspace>/brief.md         供 Agent 阅读的合并素材
  <workspace>/assets/          本地图片（复制或下载）

用法：
  python3 ingest.py [--workspace DIR] [--images a.jpg,b.png] [--links URL] [--text "..."]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".agents" / "data" / "xhs-content-studio" / "workspace"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MAX_LINK_CHARS = 6000


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in re.split(r"[,\n]", value) if p.strip()]


def make_workspace(explicit: str | None) -> Path:
    if explicit:
        ws = Path(explicit).expanduser().resolve()
    else:
        ws = DEFAULT_ROOT / time.strftime("%Y%m%d-%H%M%S")
    (ws / "assets").mkdir(parents=True, exist_ok=True)
    return ws


def fetch(url: str, timeout: int = 20) -> tuple[bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://www.xiaohongshu.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def ext_from(content_type: str, url: str, default: str = ".jpg") -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "gif" in ct:
        return ".gif"
    suffix = Path(url.split("?")[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else default


def save_image(src: str, assets: Path, index: int) -> dict:
    entry: dict = {"source": src, "path": None, "ok": False, "error": None}
    if re.match(r"^https?://", src, re.I):
        try:
            data, ct = fetch(src)
            dest = assets / f"img{index:02d}{ext_from(ct, src)}"
            dest.write_bytes(data)
            entry.update(path=str(dest), ok=True)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            entry["error"] = f"下载失败: {exc}"
    else:
        p = Path(src).expanduser()
        if p.is_file():
            dest = assets / f"img{index:02d}{p.suffix.lower() or '.jpg'}"
            shutil.copy2(p, dest)
            entry.update(path=str(dest), ok=True)
        else:
            entry["error"] = "本地文件不存在"
    return entry


def strip_html(raw: str) -> tuple[str, str]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    title = html.unescape(title_m.group(1)).strip() if title_m else ""
    body = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    body = re.sub(r"(?is)<br\s*/?>", "\n", body)
    body = re.sub(r"(?is)</(p|div|li|h[1-6])>", "\n", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t\u00a0]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n", body).strip()
    return title, body


def read_link(url: str) -> dict:
    entry: dict = {"url": url, "title": "", "text": "", "ok": False, "error": None}
    try:
        data, _ = fetch(url)
        raw = data.decode("utf-8", errors="replace")
        title, text = strip_html(raw)
        entry.update(title=title, text=text[:MAX_LINK_CHARS], ok=True)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        entry["error"] = f"抓取失败: {exc}"
    return entry


def build_brief(materials: dict) -> str:
    lines = ["# 素材汇总", ""]
    if materials.get("text"):
        lines += ["## 用户文字", "", materials["text"], ""]
    if materials["images"]:
        lines += ["## 图片", ""]
        for img in materials["images"]:
            state = img["path"] if img["ok"] else f"(不可用: {img['error']})"
            lines.append(f"- {state}")
        lines.append("")
    if materials["links"]:
        lines += ["## 链接", ""]
        for link in materials["links"]:
            if link["ok"]:
                lines += [f"### {link['title'] or link['url']}", "", f"来源: {link['url']}", "", link["text"], ""]
            else:
                lines += [f"### {link['url']}", "", f"(抓取失败: {link['error']})", ""]
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="汇总小红书素材到工作区")
    ap.add_argument("--workspace", help="指定工作区目录（默认自动生成时间戳目录）")
    ap.add_argument("--images", help="图片路径或 URL，逗号/换行分隔")
    ap.add_argument("--links", help="链接 URL，逗号/换行分隔")
    ap.add_argument("--text", help="用户提供的文字素材")
    args = ap.parse_args()

    ws = make_workspace(args.workspace)
    assets = ws / "assets"

    materials: dict = {"workspace": str(ws), "text": (args.text or "").strip(), "images": [], "links": []}
    for i, src in enumerate(split_csv(args.images), 1):
        materials["images"].append(save_image(src, assets, i))
    for url in split_csv(args.links):
        materials["links"].append(read_link(url))

    (ws / "materials.json").write_text(json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")
    (ws / "brief.md").write_text(build_brief(materials), encoding="utf-8")

    summary = {
        "status": "ok",
        "workspace": str(ws),
        "brief": str(ws / "brief.md"),
        "materials_json": str(ws / "materials.json"),
        "image_count": sum(1 for i in materials["images"] if i["ok"]),
        "image_failures": [i for i in materials["images"] if not i["ok"]],
        "link_count": sum(1 for l in materials["links"] if l["ok"]),
        "link_failures": [l for l in materials["links"] if not l["ok"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
