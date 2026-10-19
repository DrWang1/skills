# 技能库

面向 AI 编程代理的个人开源技能集合。

## 技能

| 技能 | 说明 |
|---|---|
| [`deepseek-search`](./skills/deepseek-search) | DeepSeek 自研搜索引擎的检索与抓取工具（Search / Fetch API），返回带相关性分（rerank_score）与权威分（authority）的结构化结果，支持 site: / lang: / after: / before: / 精确短语等操作符。**仅当用户明确点名调用时才使用**——触发语为"用 ds 搜索""用 ds 搜""用 deepseek 搜索""用 DeepSeek 搜一下""走 deepseek 检索"等同义明确指令。用户只说"搜一下""查一下""帮我找找""最新消息是什么"等未点名本工具时，**不要使用本技能**，改用默认搜索能力或直接回答。Explicit opt-in only: invoke solely when the user names DS/DeepSeek search; never auto-invoke for generic search requests. |

## 许可证

[MIT](./LICENSE)
