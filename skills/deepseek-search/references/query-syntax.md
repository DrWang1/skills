# 查询操作符与检索策略

操作符直接写在 `query` 里，会原样传给搜索服务，可在一条 query 中组合多个。

| 操作符 | 示例 | 作用 |
|---|---|---|
| `site:` | `DeepSeek site:github.com` | 限定站点；多个用空格分隔并以 `OR` 连接：`site:github.com OR site:huggingface.co` |
| `-site:` | `DeepSeek -site:example.com` | 排除站点，多个用空格分隔 |
| `-` | `DeepSeek -广告` | 排除含该词的页面，多个用空格分隔 |
| `"..."` | `DeepSeek "精确短语"` | 精确匹配短语，多个用空格分隔 |
| `-"..."` | `DeepSeek -"release notes"` | 排除含该短语的页面 |
| `lang:` | `DeepSeek lang:zh,en` | 限定语言，多语言逗号分隔 |
| `after:` | `DeepSeek after:2025` / `after:2025-01-01` | 只保留该日期**之后**发布 |
| `before:` | `DeepSeek before:2026-06-01` | 只保留该日期**之前**发布 |

## 组合示例

```text
# 官方政策原文，近一年，中文
广西 医保 双通道 药店 site:gov.cn lang:zh after:2025-01-01

# 技术方案，只要 GitHub/HF，排除中文二手解读
search api site:github.com OR site:huggingface.co lang:en

# 财报口径，排除券商研报聚合站
一心堂 半年报 门店数 -site:eastmoney.com -研报
```

## 检索策略

**先宽后窄。** 第一次别堆操作符——先看搜索引擎怎么理解，再决定要不要加 `site:` / `after:`。空结果通常不是没资料，是 query 太窄。

**权威分怎么用。**
- `authority = 4`：政府机关、官方机构、原始发布方 → 政策/法规/公告优先取这类
- `authority = 3`：正规媒体、企业官网
- `authority = 2`：一般媒体、行业站
- `authority ≤ 1`：自媒体、聚合、内容农场 → 只作线索，不作依据

**相关分怎么用。** `rerank_score ≥ 1.5` 才值得读；1.5 以下通常是关键词碰巧命中，别浪费抓取次数。

**中文场景的两个高频套路：**

1. 政策类：`<主题> site:gov.cn lang:zh` → 命中省/市级医保局、药监局原文，比二手解读准。
2. 上市公司数据类：`<公司> <报告期> <指标>` → 先拿摘要判断口径（合并/母公司、含税/不含税），再 `fetch` 原文核对表格。

**省一次抓取。** 要正文但不想多花一次请求时，用 `--content --content-chars N` 让 Search 直接带正文摘录（`need_content=true`）。代价是需要时会返回整页正文、token 变多，所以 `content_chars` 控制输出长度。

## 与内置搜索的分工

本技能**是用户点名才用的专用通道**：用户说"用 ds 搜索"时才走这里。它给的是「这条能不能当证据」的答案——凡结论要对外、要引用、要经得起追问，用它并保留 URL。

用户只说"搜一下""查一下"时，走默认搜索，不要自行切换到这里。
