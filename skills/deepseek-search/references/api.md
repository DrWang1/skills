# Search / Fetch API 参考

Base URL：`https://api.deepseek.com`
鉴权：`Authorization: Bearer <DEEPSEEK_API_KEY>` + `Content-Type: application/json`
两者都是只读接口，错误格式与 OpenAI 兼容（`param` 恒为 `null`）。

## Search

`POST /v1/tools/search`

### 请求字段

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `query` | string | 是 | — | 1~128 Unicode 字符，不能全空白，支持查询操作符 |
| `count` | integer | 否 | 10 | 1~50，只影响返回条数，**不影响计费** |
| `ori_question` | string | 否 | — | 触发搜索的用户原始问题，1~128 字符，提升意图理解；传 `null` 视为未提供 |
| `localization` | string | 否 | `""` | 用于地域化结果的 IP 地址 |
| `need_content` | boolean | 否 | false | 是否在 `content` 返回正文；false 时 `content` 恒为空字符串 |

未知字段会被忽略。

### 响应字段（`results[]`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `rerank_score` | number | 0~3，综合相关性/权威性/时效性；**≥1.5 为优质** |
| `title` | string | 标题 |
| `url` | string | 链接 |
| `snippet` | string | 短摘要，约 100~200 字符，适合展示 |
| `summary` | string | 长摘要，约 600~800 字符，**适合直接喂给模型** |
| `content` | string | 正文，需 `need_content=true`；缺失时为空串 |
| `site_name` | string/null | 站点名 |
| `site_icon` | string/null | favicon URL |
| `date` | string/null | 发布时间，UTC RFC 3339 |
| `authority` | integer | 0~4，**≥3 为极权威**；`-1` 表示未知 |

正常但无匹配时返回空数组（HTTP 200，不计费）。

## Fetch

`POST /v1/tools/fetch`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | 是 | ≤8192 字符，必须是含 host 的 HTTP/HTTPS URL，不能带用户名密码 |

响应：`{ "title": string, "content": string }`，失败时 `title` 为空串。

**已知坑**：`content` 里的标点在代码块外被 markdown 转义（`https\:\/\/api\.deepseek\.com`、`\- 列表`）。本技能默认在代码块外还原（`unescapeMarkdown`），要原样输出用 `--raw`。

## 错误码

| 状态 | 含义 | 处理 |
|---|---|---|
| 400 | 请求头/体不合法，含 JSON 格式错误、字段值越界 | 改请求，别重试 |
| 401 | key 缺失或无效 | 换 key |
| 402 | 余额不足 | 充值后重试 |
| 403 | Fetch 被安全策略拒绝 | 换 URL |
| 404 | Fetch 取不到可用内容：URL 不可用、被站点策略拦截、目标站报错、内容类型不支持、抽不出正文 | **换源，别重试** |
| 408 | 读取请求体超时 | 退避重试 |
| 413 | 请求体过大 | 改请求 |
| 429 | 超出 Search/Fetch QPS | 退避重试 |
| 500 | 服务端内部错误 | 退避重试 |
| 504 | 下游超时 | 退避重试 |

脚本对 408 / 429 / 5xx 做 2 次指数退避（0.5s、1s）；其余 4xx 直接抛错。

## 计费

| 接口 | 单价 |
|---|---|
| Search | 5 元 / 1000 次成功请求 |
| Fetch | 5 元 / 1000 次成功请求 |

计费条件：HTTP 200 **且**产生结果（Search 的 `results` 非空、Fetch 返回正文）。失败、空结果、超时都不计费。

## 限流

按账号粒度，Search 与 Fetch **独立计数**，与模型并发限制无关；Fetch 另有单域名 QPS 限制。

- 官方指南页：Search 100 QPS、Fetch 25 QPS
- 官方支持文档（被 IT之家等引述）：两者各 5 QPS

口径不一致 → 按 5 QPS 保守调用，撞 429 会明确返回。

## 免费窗口（不适用于本技能）

经 DeepSeek Harness / Claude Code / Codex 触发的服务端 Search/Fetch 调用，免费至北京时间 2026-11-01 00:00，之后按次计费。本技能是**直连 API**，从第一次调用即计费。
