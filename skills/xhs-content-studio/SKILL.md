---
name: xhs-content-studio
description: 小红书内容工作台。把用户发来的素材（图片 / 链接 / 文字）整理成一篇小红书笔记（标题、正文、标签、配图/封面），展示预览并等待用户明确确认后，再调用发布底座自动发布到小红书账号。当用户说"发小红书""帮我发篇笔记""把这些素材做成小红书""根据这个链接写笔记发出去""xiaohongshu / 小红书 / rednote 发布"等指令时使用此技能。
license: MIT
metadata:
  author: wangzhengjing
  version: 1.1.0
  created: 2026-09-15
  updated: 2026-09-16
  language: zh_CN
  requires:
    - xiaohongshu-skill（发布底座，默认 ~/.agents/skills/xiaohongshu-skill）
---

# xhs-content-studio — 小红书内容工作台

把素材变成可发布的小红书笔记，并且**只在用户明确确认后**才发布。

## 依赖与安装

### 本技能自身
- 仅依赖 **Python 3.10+ 标准库**（`ingest.py` / `publish.py` 无需第三方包）。
- 封面渲染 `render_cover.py` 复用发布底座的环境（Playwright + markdown）。

### 发布底座（必需）
通过第三方仓库 `DeliciousBuding/xiaohongshu-skill` 实际发布。
默认路径 `~/.agents/skills/xiaohongshu-skill`，可用环境变量 `XHS_SKILL_DIR` 覆盖。

**运行环境**：
- 必需：Python ≥ 3.10、[uv](https://docs.astral.sh/uv/)（文档命令基于 uv；亦可用 pip + venv 替代）、可联网
- 平台：macOS / Linux / Windows 均可
- 无需预装 Chrome，Playwright 会自带 Chromium

**安装步骤**：

```bash
# 1) 放入 skills 目录
git clone https://github.com/DeliciousBuding/xiaohongshu-skill.git \
  ~/.agents/skills/xiaohongshu-skill
# 网络慢可改用 ZIP：
#   https://github.com/DeliciousBuding/xiaohongshu-skill/archive/refs/heads/main.tar.gz

# 2) 安装 Python 依赖（国内镜像加速）
cd ~/.agents/skills/xiaohongshu-skill
UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple" \
  uv sync --frozen --no-dev
# 官方源：去掉 UV_DEFAULT_INDEX=... 直接 uv sync --frozen --no-dev

# 3) 安装 Playwright Chromium（国内镜像加速）
PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright" \
  uv run playwright install chromium
# 官方源：去掉 PLAYWRIGHT_DOWNLOAD_HOST=... 直接 uv run playwright install chromium

# 4) 首次扫码登录（会打开浏览器，用手机扫码）
uv run python -m scripts qrcode --headless=false

# 5) 验证登录
uv run python -m scripts check-login      # 期望 "is_logged_in": true
```

多账号：登录/发布时加 `--profile <名字>` 隔离。

### 环境变量
| 变量 | 作用 | 默认 |
|---|---|---|
| `XHS_SKILL_DIR` | 发布底座路径 | `~/.agents/skills/xiaohongshu-skill` |
| `XHS_PROFILE` | 账号 profile | 默认账号 |

### 安装自检
```bash
python3 <skill_base_dir>/scripts/ingest.py --text "自检"   # 期望 "status": "ok"
cd ~/.agents/skills/xiaohongshu-skill && uv run python -m scripts check-login
```

## 核心流程（必须按顺序执行）

```
素材(图片/链接/文字)
  1. ingest     → 汇总到工作区，产出 brief.md
  2. 生成草稿   → 标题 / 正文 / 标签（用当前模型写，参考 references/writing-guide.md）
  3. render     → Markdown 渲染成 1080 配图/封面（或直接用用户素材图）
  4. 预览确认   → 展示给用户，等待"确认"
  5. publish    → 确认后加 --confirm 真正发布
```

### 第 1 步：汇总素材

```bash
python3 <skill_base_dir>/scripts/ingest.py \
  --images "a.jpg,https://example.com/b.png" \
  --links "https://www.xiaohongshu.com/explore/xxx" \
  --text "用户给的文字"
```

产出（默认 `~/.agents/data/xhs-content-studio/workspace/<时间戳>/`）：
- `brief.md`：合并后的素材，**先读这个再写稿**
- `materials.json`：结构化素材
- `assets/`：本地图片

### 第 2 步：生成草稿

用当前 Agent 的模型直接写，遵循 `references/writing-guide.md`：
- 标题 ≤ 20 字，带情绪/数字/钩子
- 正文分段短句，开头 2 行抓人，结尾引导互动
- 3–8 个精准标签
- 把草稿写入 `<workspace>/note.md`（Markdown）

### 第 3 步：生成配图/封面

用底座把 `note.md` 渲染成 1080 宽图片（**不打开浏览器、不发布**）：

```bash
uv run --project ~/.agents/skills/xiaohongshu-skill \
  python <skill_base_dir>/scripts/render_cover.py \
  --file <workspace>/note.md --outdir <workspace>/assets --width 1080
```

若用户直接提供了图片，可直接用这些图片，跳过渲染。

### 第 4 步：预览并等待确认（关键！）

向用户展示一张预览卡片，字段齐全：

```
【账号】<profile 或 默认>
【标题】...
【正文】...
【标签】#a #b #c
【图片】<绝对路径列表>
【可见范围】默认公开
```

**在用户回复明确的"确认/可以发/发吧"之前，禁止执行第 5 步。**
任何写操作（发布/评论/点赞/收藏）都必须先确认。

### 第 5 步：发布

先不带 `--confirm` 跑一次，确认参数正确：

```bash
python3 <skill_base_dir>/scripts/publish.py \
  --title "标题" --content "正文" --images "a.jpg,b.jpg" --tags "标签1,标签2"
```

用户确认后追加 `--confirm`：

```bash
python3 <skill_base_dir>/scripts/publish.py \
  --title "标题" --content "正文" --images "a.jpg,b.jpg" --tags "标签1,标签2" \
  --confirm [--profile <账号>] [--schedule-time "2025-01-01 12:00"]
```

Markdown 发布模式：`--mode md --title "标题" --file <workspace>/note.md --confirm`
长文模式：`--mode longform --title "标题" --content "正文" --confirm`

## 发布状态处理（严格）

| status | 含义 | 动作 |
|---|---|---|
| `confirmed` | 观察到可信成功信号 | 告知用户发布成功 |
| `ready` | 已填表未提交 | 等用户确认后加 `--confirm` |
| `submitted_unconfirmed` | 已点提交但未确认 | **人工到 App/网页复核，禁止自动重试** |
| `failed` / `error` | 失败 | 停止，转人工 |
| `captcha_required` | 触发验证码/安全验证 | **立即停止，转人工处理，不得绕过** |

## 红线

1. 未确认不发布。每次只执行用户确认过的**单次**操作。
2. 遇验证码 / 登录页 / 安全验证 → 停止，转人工。
3. 不读取、展示、外发本地账号状态、Cookie、二维码等敏感信息。
4. 控制发布频率，避免批量操作触发风控。自动化发布存在**限流/封号**风险，建议先用测试号。
5. 素材涉及版权图 / 敏感内容时，在预览环节提示用户把关。

## 参考

- `references/writing-guide.md`：小红书文案写法与标签规范
- 发布底座文档：`~/.agents/skills/xiaohongshu-skill/docs/API.md`
- 发布底座安装与平台说明：`~/.agents/skills/xiaohongshu-skill/docs/INSTALL.md`
