---
name: portfolio-checkup
description: 生成股票/持仓「体检报告」单页 HTML——对一组标的做估值、基本面、资金、技术四维打分，输出保留/观察/减仓判断、相关性矩阵、组合结构分析与加减仓优先级，含 ECharts 图表。当用户说"持仓体检""帮我诊断哪只该砍""XX 该不该减仓""组合风险分析""五只票哪个最弱""持仓体检报告"时使用。也可用于单只标的的四维快速体检。
metadata:
  author: wangzhengjing
  version: 1.1.0
  created: 2026-09-15
  updated: 2026-09-16
  language: zh_CN, en_US
  agent_created: true
---

# portfolio-checkup — 持仓体检报告

把「这堆票里哪只该砍 / 这个账户结构有没有问题」变成一个**可复算、可跨期对比**的量化流程，而不是凭感觉排序。

## 默认交付形态（硬要求）

**只要用户提到"分析持仓 / 体检 / 看看我的账户 / 哪只该砍"，默认交付单页 HTML 报告，不是聊天里的长文分析。**

- 聊天回复只给：**核心结论（3–5 条）+ 关键数字 + 报告文件路径**，不要把所有分析都堆在对话里
- 报告必须是**单文件 HTML**（ECharts 内嵌、可离线打开、浏览器面板可直接预览）
- 只有用户明确说"不用出报告，简单说说"时才降级为纯对话

这是本技能与"随口分析一下"的根本区别：交付物是报告，对话只是摘要。

## 两种报告模式（先路由再动手）

| 用户真正问的是 | 模式 | 模板 | 构建脚本 |
|---|---|---|---|
| 「这几只票哪只该砍 / 该减 / 该留」——**标的之间比优劣** | `screening` 选股模式 | `references/template.html` | `scripts/score.py` → `scripts/build.py` |
| 「我这个账户结构有没有问题 / 风险在哪」——**组合层面看暴露** | `structure` 结构模式 | `references/template-structure.html` | `scripts/build_structure.py` |

**判定规则**：如果组合里有杠杆 ETF、多币种、或单一标的权重 >30%，优先用 `structure` 模式——此时"哪只票好"不是主要矛盾，"钱压在哪、有没有杠杆、有没有重复下注"才是。

两种模式都要输出：数据来源与口径章、免责声明章、**数据缺口章（取不到的数据必须列出来，不许用训练数据填）**。

---

## 产出物

单文件 HTML，含：结论速览卡、总览表、增长-估值气泡图、四维得分图、主力资金图、涨跌超额图、相关性热力图、逐只体检卡、组合结构、加减仓优先级、稳健性检验。
（`structure` 模式则替换为：账户 KPI、持仓明细、**穿透敞口图**、杠杆衰减专题、估值位置图、权重与盈亏图、逐只点评、跨账户叠加、优先级。）

---

## 何时用

- 用户给定一组标的，问「哪只该砍 / 该减 / 该留」
- 定期（月度/季度）复盘同一组标的，想和上期对比
- 想看组合层面的相关性、集中度、整体风险
- 单只标的的四维快速体检（把 stocks 数组写成 1 只即可，但相关性热力图会失效，需删掉该章节）
- 看券商实盘账户（老虎证券等）的持仓结构

---

## 六步流程

> 下面按 `screening` 模式写。`structure` 模式**跳过 Step 3–4**（没有四维打分环节），从 Step 2 直接到 Step 5：取完数后组装 `payload.json`，再 `build_structure.py` 构建，最后同样要做 Step 6 验证。
> Step 1（确认标的池）与 Step 6（验证）两种模式都要做。

### Step 1 — 确定标的池与指数基准

**先确认一件事：这是实盘持仓，还是举例／测试？**

这一步不能省。用户说"帮我体检这五只"时，可能是真实持仓，也可能只是想看看报告长什么样。
两者产出的文件必须区分开——因为**实盘报告可以作为后续分析的输入，测试报告绝对不能**。
把测试组合当实盘引用，会凭空造出"跨账户叠加"这类看似有洞察、实则前提是假的结论。

向用户确认：标的清单、**实盘还是举例**、有没有仓位权重、指数基准（默认沪深300）。
- 实盘：报告命名带账户标识（如 `老虎账户持仓体检.html`），结论可作为后续输入
- 举例／测试：报告命名带 `样例` / `demo`，并在报告里标注"非实盘数据"，**禁止被后续报告引用**
**没有仓位权重也能做**，但要显式说明结论建立在「等权假设」上——这是最常见的误用点。

### Step 2 — 取数（两条链路，不要混）

**A. 行情 / 资金 / 技术** → 腾讯自选股接口

```bash
# 收盘价（quote 子命令在本渠道不可用，用 asfund 的 ClosePrice 兜底）
npx -y westock-data-clawhub@1.0.4 asfund sh600519,sz300750 --date 2026-09-15
# K线（区间涨跌幅 + 相关性矩阵的原料）
npx -y westock-data-clawhub@1.0.4 kline sh600519,sz300750 --period day --limit 250
# 技术指标
npx -y westock-data-clawhub@1.0.4 technical sh600519,sz300750 --group ma,macd,rsi,kdj,boll
# 分红（算股息率用，取近 12 个月已实施方案）
npx -y westock-data-clawhub@1.0.4 dividend sh600519,sz300750
# 指数基准
npx -y westock-data-clawhub@1.0.4 kline sh000300 --period day --limit 25
```

**B. 估值 / 财务** → NeoData（走 `neodata-financial-search` 技能）

```bash
python3 <neodata-skill>/scripts/query.py --query "贵州茅台 600519 最新滚动市盈率PE-TTM、市盈率历史分位数、市净率PB、PB历史分位数" --data-type api
python3 <neodata-skill>/scripts/query.py --query "贵州茅台 600519 2025年报 加权净资产收益率ROE、销售净利率、销售毛利率、营业收入同比增长、归母净利润同比增长、资产负债率、流动比率" --data-type api
python3 <neodata-skill>/scripts/query.py --query "宁德时代、比亚迪 近期股价下跌原因 最新消息" --data-type doc
```

第三条（`--data-type doc`）**建议不要省**：它能解释「跌得最多那只是不是有事件驱动」，让报告从「数据罗列」变成「有归因」。这是报告质感差异最大的一步。

### Step 3 — 组装 raw.json

把 Step 2 的数字填进 `raw.json`（字段口径见 `references/field-map.md`，务必对齐，否则分数不可跨期比）。
示例见 `references/example-raw-input.json`。

**资金维度必须填 `mcap`（总市值）** —— 不用市值归一，大盘股和小盘股的净流入绝对值不可比，会系统性误判大市值标的"更安全"。实测案例：恒瑞净流出 54.7 亿看似与茅台 22.4 亿同量级，但归一后是 1.91% vs 0.14%，差 13.6 倍。

### Step 4 — 打分

```bash
SK=<skill目录>
python3 $SK/scripts/score.py raw.json kline.txt --sensitivity   # 先看结论稳不稳
python3 $SK/scripts/score.py raw.json kline.txt > data.json     # 正式打分
```

`--sensitivity` 是**必做步骤**：它会扫描基本面质量权重，告诉你「谁垫底」在什么权重区间会翻转。把结果写进报告的稳健性检验块——**权重是主观的，不交代适用范围等于藏了一个假设。**

### Step 5 — 写文案并构建

**`screening` 模式**：写 `narration.json`。契约见 `scripts/build.py` 顶部 docstring，**完整可直接抄的样例见 `references/example-narration.json`**（203 行，一次真实交付的全部文案）。

narration.json 分两层：

| 层 | 键 | 内容 |
|---|---|---|
| 章节级 | `_title` `_asof` `_dims` `_ccy` `_hero` `_footer` | 标题、时点、维度、Hero 总结、页脚 |
| 章节级 | `_note_s3` ~ `_note_s7` | 5 张图表下方的「读图」解读段 |
| 章节级 | `_portfolio` `_steps` `_questions` `_sources` | 09 组合视角卡片 / 10 优先级 / 11 前提追问 / 12 数据来源，**由 build.py 服务端渲染，序号自动生成** |
| 章节级 | `_sensitivity` | 稳健性检验块；**整体省略则该章节自动删除**，不会留空卡片 |
| 个股级 | `sh600519` 等 code 键 | `vtag` `verdict` `why` `val` `qual` `flow` `tech` `call` |

**`__N__` `__SYMS__` `__ASOF__` `__FY__` `__CORR_SPAN__` 等派生字段由 `score.py` 自动产出**（从 `raw.json` 的 `stocks` 与可选的 `asof` / `fy` / `ccy` 推得），**不需要在文案里手写数量词**——标的不等于 5 只时模板会自动适配。

```bash
python3 $SK/scripts/build.py data.json $SK/references/template.html \
    $SK/assets/echarts.min.js 持仓体检报告.html narration.json
```

构建脚本会检查：残留占位符、缺个股文案、缺章节块、缺 `fy`、缺相关矩阵——**任何一条报警都不应交付**。

**`structure` 模式**：写 `payload.json`，分 `_text`（文本占位符）与 `_data`（注入 JS 的数据对象）两段。契约见 `scripts/build_structure.py` 顶部 docstring，**完整样例见 `references/example-payload-structure.json`**（524 行）。

| 段 | 键 | 内容 |
|---|---|---|
| `_text` | `TITLE` `ACCOUNT` `ASOF` `TODAY` `SYMS` `HERO` | 标题、账户号、时点、Hero 总结 |
| `_text` | `CCY_SYM` `FX_NOTE` `FX` `POS_LEDE` `P30_RANGE` `PE_NOTE` | 计价货币符号与口径说明 |
| `_text` | `EXP_LEDE` `LEV_TITLE` `LEV_NOTE` `LEV_READING` | 穿透敞口与杠杆专项的措辞（**杠杆标的名只出现在这里，不写进模板**） |
| `_text` | `EXPOSURE_NOTE` `VAL_NOTE` `ATTRIB_NOTE` | 各图读图 |
| `_text` | `CROSS_TITLE` `CROSS_LEDE` `GAPS` `DISCLAIMER` `FOOTER` | 跨账户 / 缺口 / 免责 / 页脚 |
| `_data` | `account` `positions` `exposure` `tqqq` `valuation` `details` `steps` `cross` `sources` | 数据对象 |

要点：
- `exposure.groups` 是**堆叠顺序 + 图例色**的单一来源（`[{name,color}]`），图例会自动渲染，不用手写 `EXP_LEGEND`
- `tqqq.decay.levName` / `levMult` 驱动图表文案（`理论 3 倍` / `TQQQ 实际`），**模板里没有任何产品名**
- `_data.cross` 是 08 节卡片、`sources` 是 10 节 bullet，均由脚本服务端渲染
- `valuation` 里 `pe: null` 的标的会被 JS 自动过滤（ETF 或无有效口径的标的）

```bash
python3 $SK/scripts/build_structure.py payload.json \
    $SK/references/template-structure.html $SK/assets/echarts.min.js \
    账户持仓体检.html
```

> 脚本会逐条检查缺失的 `_text` / `_data` 键、缺失的 `exposure.groups` / `segs`、以及残留占位符——**任何一条报警都不应交付**。

**文案写作要点**（决定报告可用性）：
- 每个数字后面接「所以呢」——不是「PE 40.69% 分位」，而是「PE 分位 40.69% 是五只最高，但这是因为分母盈利在缩水，PE 被动抬高」
- 判断必须给**触发条件**，不能只说"观察"。例：「20 日净流出强度收敛至 0.5% 以内，或价格重新站上 MA60 附近，再考虑回补」
- **主动写异议点**。例：某只标的 PB 仅 0.58% 分位，砍它可能是砍在底部——把这个反过来告诉用户，比单边喊砍更可信
- **低 PE 要怀疑分母**。看到「估值历史最低」先问一句：是价格跌了，还是盈利要跌？用旧盈利算出的低 PE 是价值陷阱的标准形态，必须写成风险而不是机会
- 结尾固定写「不构成投资建议」

### Step 6 — 验证（不可省）

```bash
export PATH="<node>/bin:$PATH"
agent-browser open "file:///<abs-path>/持仓体检报告.html"
agent-browser eval "JSON.stringify({c:document.querySelectorAll('canvas').length,sw:document.body.scrollWidth,cw:document.documentElement.clientWidth})"
agent-browser close
```

必查项：canvas 数量 = 图表数；`scrollWidth == clientWidth`（无横向溢出）；各卡片/表格行数量与标的数一致。
**长文档交付物不要靠截图检查——用 `eval` 程序化校验更可靠**（尤其当模型本身读不了图片时）。

---

## 踩坑清单（都是实际踩过的）

| 坑 | 现象 | 修法 |
|---|---|---|
| **kline 列序** | 区间涨跌幅全错 | 列为 `symbol\|date\|open\|last\|high\|low\|volume\|amount\|exchange`，**收盘价是第 4 列（索引 3）**，不是第 5 列。`:---:` |
| **neodata 多股估值只回一只** | 五只只拿到第一只的 PE | 「统一估值查询」必须**逐只单独查** |
| **neodata 财务块最多 4 只** | 第 5 只（常是茅台）缺失 | 单独补查一次，或分批查 |
| **Markdown 表分隔行** | 取到的值全是 `:---:` | 表结构是「表头 + 分隔行 + 数据行」，解析时剔除纯分隔行，并按表头名索引取值 |
| **相关矩阵顺序错位** | 热力图上数值落错格子 | 打分函数会先算矩阵再按总分排序；若矩阵顺序取自排序前、页面顺序取自排序后，**必须在 build 阶段重排矩阵** |
| **`quote` 子命令不可用** | `命令 "quote" 在当前渠道不可用` | 用 `asfund` 的 `ClosePrice` 或 `kline` 取收盘价 |
| **图表端标签被裁** | ECharts `endLabel` 贴右边被画布切掉 | grid `right` 留白 ≥ 130px，或改用 legend |
| **权重未做敏感性检验** | 报告结论看似果断，其实换个权重就翻转 | 必跑 `--sensitivity`，并把结论写进报告 |
| **沿用上期文案** | 结论对不上本期数据 | 每月必须重跑 Step 2–4；**只复用报告结构，不复用结论文字** |
| **把测试组合当实盘引用** | 凭空造出"跨账户叠加"等假结论 | Step 1 必须问清实盘还是举例；样例产物命名带「样例／非实盘」并在报告内显著标注；**样例不得被后续报告引用** |

---

## 评分模型摘要

```
综合分 = 基本面质量×45% + 资金动向×20% + 估值×20% + 技术位置×15%

基本面质量 = ROE .22 + 净利率 .12 + 毛利率 .08 + 净利增速 .25 + 负债率 .15(反向) + 流动比率 .10 + 自由现金流 .08
资金动向   = 20日净流入/市值 .70 + 5日 .15 + 当日 .15      （按市值归一是关键）
估值性价比 = (100 − 0.5×PE分位 − 0.5×PB分位) .90 + 股息率映射 .10
技术位置   = 20日超额收益 .40 + 距MA250 .30 + MACD/价 .15 + RSI6 .15
```

**为什么用绝对锚定而不是截面 min-max**：5 只标的做 min-max 会把最高分强行拉到 100、最低压到 0，制造虚假的极端值（实测第一版茅台直接 100 分、立讯 10 分，看着"果断"其实是人为拉伸）。绝对锚定（如 ROE 35% 记满分、净利增速 +45% 记满分、负债率 80% 记 0 分）让**分数本身可跨期复算、可与后续月份直接对比**——这是做定期体检的前提。

**权重设计的理由**：问题问的是"该不该持有"（中长期判断），所以基本面质量给到 45%；资金与技术是战术层面、会均值回归，合计只给 35%。若用户是短周期交易视角，应把权重重配并**重跑敏感性检验**。

---

## 输出规范

- 简体中文；表格表头沿用源接口英文字段名时保留英文
- **涨红跌绿**（中国股市惯例）：涨/正向用红 `#d8493f`，跌/负向用绿 `#21a675`
- 货币单位 ¥；金额统一亿元
- 数据来源与口径单独成章，写清每个字段来自哪个接口、什么口径（年报 / 收盘 / 近 12 个月）
- 免责声明必写

---

## 非 A 股组合（港股 / 美股）注意事项

本 skill 的取数链路是为 A 股设计的。换成港股/美股组合时，以下四点必须先解决，否则分数不可比：

1. **多币种必须先统一**。组合里混 HKD/USD/CNY 时，任意两个数字直接相加都是错的。
   - 拿不到直接汇率时，可用券商接口反推：`FX = 单一币种持仓市值 / (总持仓市值 − 其他币种持仓市值折算值)`
   - 实测案例：由老虎 `gross_position_value` 反推出 HKD/USD = 7.8474
   - **报告中必须写明汇率取值与反推方法**，因为它是所有港币持仓权重的前提。

2. **杠杆 ETF 必须按名义敞口穿透**，不能按市值计权重。
   - 2 倍/3 倍日重置 ETF（TQQQ、SQQQ、SOXL 等）名义敞口 = 净值 × 杠杆倍数
   - 有效杠杆 = (总市值 + 杠杆 ETF 超出部分 + 现金) / 净清算
   - 还要算**标的重叠**：3 倍纳指 ETF 的底层包含你已直接持有的成分股。取纳指权重做穿透，得到"直接 + 间接"的真实集中度。
   - 检索纳指权重时注意**来源分歧**（封顶规则导致市值权重 ≠ 指数权重）。取两个独立来源一致的数值，并说明口径。

3. **每日重置 ETF 有结构性衰减**，应实测而非泛泛而谈：
   ```
   偏离 = ETF 实际区间涨跌 − 标的指数区间涨跌 × 杠杆倍数
   ```
   实测案例：QQQ 20 日 −2.83%，理论 3x = −8.50%，TQQQ 实际 −9.33%，偏离 −0.83pct。

4. **美股/港股财务数据取哪里**（实测有效的路径）：
   - `npx -y westock-data-clawhub@1.0.4 finance usAAPL --num 24` ← **美股财报可用**，返回 income / balance / cashflow 三段 Markdown 表
   - `npx -y westock-data-clawhub@1.0.4 profile usAAPL` ← 公司简介、行业、上市地
   - `npx -y westock-data-clawhub@1.0.4 finance hk01810 --num 24` ← 港股用 **zhsy / zcfz / xjll** 三段（字段名与美股不同：`RoeWeighted`、`NetProfitRatio`、`GrossIncomeRatio`、`DebtAssetsRatio`、`BasicEpsGr1y`）
   - 走不通的：neodata「统一估值查询」对美股返回空值（`--`）；老虎 `quote fundamental financial` 参数为位置参数、实测解析失败。**这两条路不要浪费时间**
   - `etf-holdings` 对美股 ETF（如 QQQ）返回「无持仓数据」——纳指权重需外部检索

5. **拿到财务数先做自洽性交叉验证**，再进评分。方法：把最新年度的营收/EPS 与已知实际值对一遍。
   - 实测通过：苹果 FY2025 营收 $416.16B ✓、EPS $7.49 ✓；英伟达 FY2025 营收 $130.50B ✓、EPS $2.97 ✓；小米 FY2025 HK$506.3B ✓
   - 实测不通过：**阿里巴巴**营收口径返回 ¥138.0B（实际约 ¥996B，差约 7 倍），说明单位或股本口径与 ADR 价格不自洽
   - **不通过就剔除该标的的估值维度并在报告中标注**，绝不用一个口径不自洽的数字去做 PE 分位

6. **PE 与估值分位可自算**（无现成分位数据时）：
   - PE(TTM) = 现价 ÷ 滚动十二个月 EPS（美股按最近 4 个季度 `BasicEPS_Q` 加总；港股按最近一个完整年度 `BasicEPS`）
   - 年度 PE 序列 = 各财年末收盘价 ÷ 当年年度 `BasicEPS`
   - 分位 = 当前 PE 在序列中的排名百分位。**必须标注样本量**（实测只有 5 个财年，属方向性参考，不是精算分位）
   - 注意：数据集的季度标签可能与公司实际财季相差一个季度（实测苹果），但**年度聚合是正确的**，TTM 用最近 4 个季度也不受影响

7. **每日重置杠杆 ETF 的衰减要实测、不要泛泛而谈**：
   ```
   衰减缺口 = ETF 实际区间涨跌 − 标的指数区间涨跌 × 杠杆倍数
   ```
   多窗口并列展示最有说服力（实测 TQQQ：近 5 日 −0.17pct → 近 20 日 −0.83pct → **近 60 日 −3.80pct**，缺口随时间放大，直接说明复利成本）。

### 老虎证券（tigeropen）专项

- 配置文件在 **`~/.tiger/`**（不是文档写的 `~/.tigeropen/`），CLI 需显式 `-c ~/.tiger`
- CLI 装在 managed venv 但**可能缺 `click`**：`<venv>/bin/pip install click`
- `trade position list` 的 `quantity` 字段对部分标的存在序列化异常（如 TQQQ 返回 1627757 而真实为 16.27757）。**一律以 `position_qty` 为准**，并用 `market_value ÷ market_price` 交叉验证
- 常用命令：`account assets`（含净清算/杠杆/保证金）、`account analytics`（区间收益与最大回撤）、`trade position list`、`quote market-status`
- **下单类命令默认禁止**：只做只读查询。若用户要交易，先 `preview_order()` 展示费用，列表格确认，并停下等明确授权

### 跨账户视角（仅当用户确认存在多个实盘账户时）

> **前置铁律：不得用测试数据、假设数据或"如果"来推断跨账户叠加。**
> 必须在用户**明确确认**另一个账户是实盘、并提供其真实持仓之后，才做跨账户分析。
> 拿不准就先只分析当前账户，并在报告里写清"本报告只覆盖 X 账户"——
> 宁可少给一个洞察，也不能凭一个不存在的账户编出"隐藏叠加"。
> （此处曾出过一次事故：把用户的一次**测试**组合当成了实盘，据此写出"苹果链双押／新能源车双押"
> 两个结论并写进了优先级步骤。看起来很有洞察力，实际前提是假的。）

确认存在多个实盘账户后，方法是：

- 按**产业链**而非行业标签归并。行业标签（"消费电子""汽车"）会把上下游拆开，产业链视角才能看出重复暴露。
- 重点查四类链条：苹果链（品牌 + 组装 + 零组件）、AI 算力（芯片 + 服务器 + 光模块 + 电力）、新能源车（整车 + 电池 + 材料）、医药（创新药 + CXO + 流通）。
- 真正要防的是**重复下注**：两个账户买同一主题的不同标的，看起来分散、实际同涨同跌。这类叠加不会出现在任何单一账户的报表里。
- 合并视图的做法：横轴按产业链分行，纵轴按账户分列，最后一列是合计暴露（含杠杆 ETF 的穿透值）。

若用户只有单账户，则把该章节写成**「本报告的边界与待确认项」**：说明覆盖范围、账户边界未确认的风险、以及要出合并视图还需补哪些输入——而不是省掉这一章。章节编号保持稳定，不要因为内容变化而跳号。

