---
name: deepseek-search
description: DeepSeek 自研搜索引擎的检索与抓取工具（Search / Fetch API），返回带相关性分（rerank_score）与权威分（authority）的结构化结果，支持 site: / lang: / after: / before: / 精确短语等操作符。**仅当用户明确点名调用时才使用**——触发语为"用 ds 搜索""用 ds 搜""用 deepseek 搜索""用 DeepSeek 搜一下""走 deepseek 检索"等同义明确指令。用户只说"搜一下""查一下""帮我找找""最新消息是什么"等未点名本工具时，**不要使用本技能**，改用默认搜索能力或直接回答。Explicit opt-in only: invoke solely when the user names DS/DeepSeek search; never auto-invoke for generic search requests.
metadata:
  author: wangzhengjing
  version: 1.1.0
  created: 2026-10-19
  updated: 2026-10-19
  language: zh_CN
  agent_created: true
---

# DeepSeek 搜索与抓取

DeepSeek 在 2026-10-17 随 V4.1-Flash-1017 开放了自研搜索引擎能力，两个端点：

| 接口 | 端点 | 作用 |
|---|---|---|
| Search | `POST /v1/tools/search` | 按 query 返回结构化网页结果（标题/URL/摘要/正文/日期/相关分/权威分） |
| Fetch | `POST /v1/tools/fetch` | 按 URL 抓单页，返回 Markdown 正文 |

本技能把它们包成一条命令，**不需要 MCP、不需要额外配置**：凭证直接复用 cc-switch 里已管理的 DeepSeek key。

## 触发规则（硬约束，优先级高于本文其他内容）

**只有用户明确点名时才调用。** 判定顺序：

1. 用户话里是否出现**明确的点名信号**？
   - ✅ 触发：`用 ds 搜索`、`用 ds 搜`、`用 deepseek 搜索`、`用 DeepSeek 搜一下`、`走 deepseek 检索`、`ds 搜个 xxx`、`用 DS 查`
   - ❌ 不触发：`搜一下`、`查一下`、`帮我搜搜`、`找找最新消息`、`这个说法对吗`、`看看官网怎么说`
2. 用户点名但**没说搜什么**（如只发了一句"用 ds 搜索"）→ 先问清 query，不要自己猜。
3. 用户点名后，**同一轮后续步骤**可以继续用本技能（例如先 search 再 fetch 同一条结果），不必每步都点名。
4. 用户没点名、但你已经判断「必须用本技能才做对」（例如结论要引用、要权威分级）→ **先问一句**「要不要用 ds 搜索？」得到同意后再用。**不要静默切换。**

理由：这个技能按次计费（5 元/1000 次），且结果格式与默认搜索不同。未经点名就调用，等于替用户花钱、替用户换口径。

## 何时用它（在被点名之后，再判断值不值得）

| 场景 | 说明 |
|---|---|
| 要判断来源可不可信 | `authority` 0~4 直接给权威分级，4 通常是政府/官方机构 |
| 要卡时间窗 / 限定站点 / 排自媒体 | `site:` `after:` `before:` `-site:` `-关键词` |
| 已知 URL 要干净全文 | `fetch` 直接给 Markdown，不用解析 HTML |
| 中文政策、公告、政府文件 | 自研索引对中文权威源覆盖好，常直接命中 `gov.cn` 原文 |

## Quick Start

```bash
NODE=node                                     # Node 18+；PATH 里没有就用绝对路径
SKILL=~/.agents/skills/deepseek-search        # 本技能目录

# 1. 先确认凭证（打印来源与 base，不打印 key）
$NODE $SKILL/scripts/ds.mjs check

# 2. 检索（默认返回 10 条，文本格式化）
$NODE $SKILL/scripts/ds.mjs search "广西 医保 双通道 药店 政策 site:gov.cn after:2026-01-01"

# 3. 只要高质量结果
$NODE $SKILL/scripts/ds.mjs search "一心堂 2026 半年报 门店数" --min-rerank 1.5 --min-authority 3

# 4. 抓正文
$NODE $SKILL/scripts/ds.mjs fetch "https://ybj.gxzf.gov.cn/..." --max-chars 8000
```

## 标准工作流：先搜、筛、再抓

1. `search` 拿候选（`count` 可到 50，反正**费用与条数无关**）。
2. 按 `rerank_score ≥ 1.5` 且 `authority ≥ 3` 筛；权威 4 通常是政府/官方机构。
3. 只对要引用的 1~3 条跑 `fetch`，不要全量抓。
4. 引用时**把 URL 原样带上**——这是可核查的凭据。

```bash
# 一步到位：只保留优质源，并附 400 字正文摘录（省一次 fetch）
$NODE $SKILL/scripts/ds.mjs search "特医食品 医保 编码 规则" \
    --count 20 --min-rerank 1.5 --min-authority 3 --content --content-chars 400
```

## 参数速查

`search`：

| 参数 | 说明 |
|---|---|
| `<query>` | 1~128 字符，支持操作符（见 `references/query-syntax.md`） |
| `--count N` | 1~50，默认 10；**不影响计费** |
| `--min-rerank N` | 只展示相关分 ≥ N 的结果，常用 1.5 |
| `--min-authority N` | 只展示权威分 ≥ N 的结果，常用 3 |
| `--content` | 让接口回正文（`need_content`） |
| `--content-chars N` | 每条附 N 字正文摘录（需配合 `--content`） |
| `--ori "<原始问题>"` | 传用户原话，提升意图理解 |
| `--json` | 输出原始 JSON，便于二次处理 |

`fetch`：`<url>`、`--max-chars N`（默认 20000）、`--raw`（不还原转义）、`--json`。

字段含义、错误码、计费与限流见 `references/api.md`。

## 凭证

四级回退，**先命中先用，不复制密钥**：

1. `DEEPSEEK_API_KEY` 环境变量（临时覆盖）
2. **`~/.cc-switch/cc-switch.db`** —— 若你也用 cc-switch 管理 API 供应商，可从其 `providers` 表取 DeepSeek 供应商下形如 `sk-…` 的值，并从 `baseURL` 归一化出 base（`/v1`、`/chat/completions`、`/anthropic` 等后缀会剥掉）；未装 cc-switch 则自动跳过
3. `~/.workbuddy/models.json` —— WorkBuddy「自定义模型」里 url 指向 `api.deepseek.com` 的那条
4. `~/.workbuddy/secrets/deepseek_api_key`

含义：在 cc-switch 或 WorkBuddy 任一处换 key / 换模型，这里**不用改任何东西**。`check` 子命令会打印当前命中哪一级：

```
$ node scripts/ds.mjs check
key 来源: cc-switch#DeepSeek
base: https://api.deepseek.com
```

cc-switch 库读取用只读方式（`sqlite3 -readonly`），不会改动它的数据；cc-switch 正在运行时也安全。

## 成本与限流

- **5 元 / 1000 次成功请求**（Search、Fetch 各算各的），空结果 / 失败 / 超时不计费。
- 一次「3 搜 + 2 抓」≈ **0.025 元**；按条数收不到钱，所以 `count` 敢给大就给大。
- QPS 口径有冲突：官方指南页写 Search 100 / Fetch 25，官方支持文档被引述为各 5 → **按 5 串行调用**，别并发。
- 经 DeepSeek Harness / Claude Code / Codex 的服务端调用有免费期（至 2026-11-01 00:00 北京时间），**本技能走直连，不享受**。

## 常见故障

| 现象 | 处理 |
|---|---|
| `HTTP 401` | key 失效，直接 `check` 看命中哪一级 |
| `HTTP 402` | 账户余额不足，去充值 |
| `HTTP 429` | 撞 QPS，退避重试（脚本已内置 2 次指数退避） |
| `HTTP 404`（fetch） | 常态，不是 bug：站点拒抓、内容类型不支持、抽不出正文。**换源，别重试** |
| 结果为空数组 | 查询太窄，去掉操作符或放宽 `after:` |
| `错误: 缺少 DeepSeek API Key` | 三级回退全落空，按提示补 |

更多排障见 `references/troubleshooting.md`。

## 可选：MCP 模式

同一份脚本支持 stdio MCP：`node scripts/ds.mjs --mcp`。若确实需要把它注册成 MCP 工具，在 `~/.workbuddy/mcp.json` 的 `mcpServers` 里加：

```json
{
  "deepseek-search": {
    "command": "<node 路径>",
    "args": ["<本技能目录>/scripts/ds.mjs", "--mcp"]
  }
}
```

并在连接器管理页点信任。**日常不需要**——走命令行更省事，也没有进程常驻。
