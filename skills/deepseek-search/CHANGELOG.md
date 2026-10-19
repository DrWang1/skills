# CHANGELOG

## 1.1.0 — 2026-10-19

- **触发收窄为显式点名**：description 与正文新增「触发规则（硬约束）」——只有用户说"用 ds 搜索 / 用 deepseek 搜索"等同义点名才调用；只说"搜一下""查一下"不触发；未点名但确有必要时须先征询。删掉原先罗列的一堆泛化触发词（"查一下最新""这条消息是真的吗"等），避免静默劫持普通检索。
- **凭证新增 cc-switch 为第 2 级来源**（优先于 WorkBuddy models.json）：只读打开 `~/.cc-switch/cc-switch.db` 的 `providers` 表，取 DeepSeek 供应商下 `sk-…` 值；`baseURL` 归一化会剥掉 `/v1`、`/chat/completions`、`/anthropic`、`/messages` 等后缀。
- `check` 输出改为显示实际命中的来源（如 `cc-switch#DeepSeek`）。
- references 同步：troubleshooting 补 cc-switch 判定条件与"点名才用"前提；query-syntax 的分工段落改为点名制口径。

## 1.0.0 — 2026-10-19

首个版本。把 DeepSeek 2026-10-17 开放的 Search / Fetch API 包成技能。

- `scripts/ds.mjs`：CLI（`check` / `search` / `fetch`）+ `--mcp` stdio 双模，零依赖（Node 18+ 原生 fetch）
- 凭证三级回退：`DEEPSEEK_API_KEY` → `~/.workbuddy/models.json` → `~/.workbuddy/secrets/deepseek_api_key`；
  命中 models.json 时自动从 `url` 反推 base（去掉 `/chat/completions`），换 key/换域名无需改脚本
- `search` 支持 count / min-rerank / min-authority / content / content-chars / ori / json
- `fetch` 默认在代码块外还原 DeepSeek 的 markdown 标点转义，保证 URL 可直接复用（`--raw` 关闭）
- 408/429/5xx 两次指数退避重试
- references/：`api.md`（字段/错误码/计费/限流）、`query-syntax.md`（操作符与检索策略）、`troubleshooting.md`（排障）
