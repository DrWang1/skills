# 排障

> 前提：本技能**只在用户点名「用 ds 搜索 / 用 deepseek 搜索」时**才调用。若用户只是说"搜一下"，不要为了排障而自行启用它——先问。

## 凭证类

**`错误: 缺少 DeepSeek API Key`**
四级回退全落空。先跑 `check` 看命中哪一级：

```bash
node scripts/ds.mjs check
# key 来源: cc-switch#DeepSeek
# base: https://api.deepseek.com
```

- 若 cc-switch 没命中：确认 `~/.cc-switch/cc-switch.db` 存在，且 `providers` 表里有一条 DeepSeek 供应商——其 `settings_config` 里要同时有 `sk-…` 形式的 key 和含 `deepseek` 的 URL，或供应商名含 deepseek。
- 若 `models.json` 没命中：确认该条目的 `url` 含 `api.deepseek.com`（不能只是模型名带 deepseek），且 `apiKey` 非空。
- 若 `check` 直接报错：临时兜底 `export DEEPSEEK_API_KEY=sk-xxx`，再去任一处补配置。

**`HTTP 401 Authentication Fails`**
key 本身失效（被删/被重置），不是读取逻辑问题。错误信息里会回显 key 尾 4 位，据此确认用的是哪一把。

**`HTTP 402`**
账户余额不足。Search/Fetch 与模型调用共用余额。

## 请求类

**`HTTP 429`**
撞 QPS。脚本已做 2 次指数退避；仍失败说明并发太高——**串行调用**，别用 `xargs -P` 之类并行。

**`HTTP 404` 集中在 Fetch**
这是常态，不是脚本 bug。以下都会归到 404：URL 已失效、站点 `robots`/风控拦截、返回的是 PDF 等不支持的内容类型、页面靠 JS 渲染抽不出正文、付费墙。

处理顺序：① 换一个来源（优先 `authority` 高的）② 该站是否必须登录 ③ 放弃抓取，改用 `search --content` 拿接口侧正文。

**结果为空数组**
HTTP 200 + 空数组，**不计费**。通常是 query 太窄：去掉 `after:`/`site:` 重试，或调大 `count`。

**`HTTP 413`**
请求体过大，检查 `url` 或参数是否异常（正常不会触发）。

## 输出类

**抓下来的正文是 `https\:\/\/…` 这种带反斜杠的**
DeepSeek Fetch 的 markdown 转义。默认已在代码块外还原；确需原样（例如要保留原始转义做对比）用 `--raw`。

**正文被截断**
`--max-chars` 默认 20000。要更多就调大；只想看开头就调小（省 token）。

**摘要和正文对不上**
`summary` 是面向模型的长摘要（600~800 字），不是原文片段，可能与正文表述有差异。需要逐字引用时必须 `fetch` 原文。

## 并发与脚本嵌入

在 agent 循环里调用时：

- 一次任务内 **最多 3 次 search + 3 次 fetch**，超出前先看已有信息够不够。
- 每个 shell 调用都要带绝对路径的 node 与脚本路径，不要依赖 `cd` 与 PATH。
- 用 `--json` 拿结构化结果便于程序分支；给人看直接用默认文本格式。

## 与 MCP 模式的关系

`--mcp` 模式是同一份脚本的另一个入口，供 MCP 客户端使用。若 MCP 未被信任或未加载，命令行模式**完全等价**，不需要任何额外授权。日常直接用命令行即可。
