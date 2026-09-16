# -*- coding: utf-8 -*-
"""
build.py — 选股模式构建器：把评分结果 + 文案注入 HTML 模板，产出单文件报告

用法:
    python3 build.py data.json references/template.html assets/echarts.min.js out.html [narration.json]

data.json     score.py 的 stdout（已含 n / syms / asof / fy / ccy 等派生字段）
narration.json 文案。下划线开头的键是「章节级文案」，其余键为股票 code 的「个股文案」：

{
  "_title":   "持仓体检 · 五只白马诊治",
  "_asof":    "2026-09-15 收盘",              // 省略则用 data.asof
  "_dims":    "估值 · 基本面 · 资金 · 技术 + 组合结构",
  "_ccy":     "元",                            // 价格单位，默认「元」
  "_hero":    "<b>结论先行：</b>…",             // Hero 区总结段
  "_note_s3": "读图：…（增长 vs 估值）",        // 各图表下方的解读段，支持 HTML
  "_note_s4": "读图：…（四维得分）",
  "_note_s5": "读图：…（主力资金）",
  "_note_s6": "读图：…（涨跌超额）",
  "_note_s7": "读图：…（相关性）",
  "_footer":  "持仓体检报告 · 生成于 …<br>…",
  "_portfolio": [                               // 09 组合视角卡片（建议 4 张）
     {"title":"分散度…","items":[{"text":"…","cls":"risk"}]}
  ],                                            // cls 可选: risk | warn | 空
  "_steps": [                                   // 10 加减仓优先级（序号自动生成）
     {"cls":"c1","ttl":"首砍 · …","tx":"…"}       // cls: c1 绿 | c2 橙 | c3 蓝
  ],
  "_questions": [ {"text":"…"} ],               // 11 前提追问（序号自动生成）
  "_sources":   [ {"text":"…"} ],               // 12 数据来源 bullet（支持 HTML）
  "_sensitivity": {                             // 稳健性检验块；整体省略则该块自动删除
     "firstcut":"比亚迪",
     "last_low":"…","last_35":"…","last_base":"…","last_high":"…","last_pure":"…",
     "s2_low":"…","s2_35":"…","s2_base":"…","s2_high":"…","s2_pure":"…",
     "note":"<b>三条可复述的结论：</b><br>① …"
  },
  "sh600519": {                                 // 个股文案
     "vtag":"防守压舱", "verdict":"保留",
     "why":"结论卡里的一句话理由",
     "val":"估值维度正文", "qual":"基本面维度正文",
     "flow":"资金维度正文", "tech":"技术维度正文",
     "call":"<b>判断：保留</b>…"
  }
}

模板占位符由本脚本统一填充，无需人工替换。缺失的章节级文案会置空并在 stderr 报警——
**不要交付带 __XXX__ 的页面**。
"""
import json, io, re, sys, os

DEFAULT_HERO = '<b>结论先行：</b>请在此填写总结段（由 narration.json 的 <code>_hero</code> 键提供）。'
SENS_KEYS = ['firstcut', 'last_low', 'last_35', 'last_base', 'last_high',
             'last_pure', 's2_low', 's2_35', 's2_base', 's2_high', 's2_pure', 'note']


# --------------------------- 块渲染器 ---------------------------
def render_portfolio(cards):
    """09 组合视角：卡片 + 要点列表"""
    if not cards:
        return ''
    out = ['<div class="pf">']
    for c in cards:
        out.append('      <div class="card">')
        out.append(f'        <h3>{c.get("title", "")}</h3>')
        out.append('        <ul>')
        for it in c.get('items', []):
            cls = f' class="{it["cls"]}"' if it.get('cls') else ''
            out.append(f'          <li{cls}>{it.get("text", "")}</li>')
        out.append('        </ul>')
        out.append('      </div>')
    out.append('    </div>')
    return '\n'.join(out)


def render_steps(steps):
    """10 加减仓优先级：序号自动生成"""
    out = []
    for i, s in enumerate(steps, 1):
        out.append(f'      <div class="step {s.get("cls", "c3")}">')
        out.append(f'        <div class="no">{i}</div>')
        out.append('        <div>')
        out.append(f'          <div class="ttl">{s.get("ttl", "")}</div>')
        out.append(f'          <div class="tx">{s.get("tx", "")}</div>')
        out.append('        </div>')
        out.append('      </div>')
    return '\n'.join(out)


def render_questions(qs):
    """11 前提追问：序号自动生成"""
    return '\n'.join(
        f'      <div class="q"><div class="n">{i}</div>'
        f'<div class="t">{q.get("text", "")}</div></div>'
        for i, q in enumerate(qs, 1))


def render_sources(src):
    return '\n'.join(f'        <li>{s.get("text", "")}</li>' for s in src)


# --------------------------- main ---------------------------
def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(1)
    data_p, tpl_p, ech_p, out_p = sys.argv[1:5]
    nar_p = sys.argv[5] if len(sys.argv) > 5 else None

    D = json.load(open(data_p, encoding='utf-8'))
    S = D['stocks']
    nar = json.load(open(nar_p, encoding='utf-8')) if nar_p and os.path.exists(nar_p) else {}

    # --- 个股文案合并 ---
    miss = []
    for s in S:
        n = nar.get(s['code'], {})
        for k in ('why', 'val', 'qual', 'flow', 'tech', 'call'):
            s['_' + k] = n.get(k, '')
        if n.get('verdict'):
            s['verdict'] = n['verdict']
        s['vtag'] = n.get('vtag') or s.get('vtag', '')
        if not n:
            miss.append(s['name'])

    tpl = io.open(tpl_p, encoding='utf-8').read()

    # --- 稳健性检验块 ---
    sens = nar.get('_sensitivity')
    if sens:
        for k in SENS_KEYS:
            tpl = tpl.replace('__' + k.upper() + '__', str(sens.get(k, '')))
    else:
        tpl = re.sub(r'<!--SENS_START-->.*?<!--SENS_END-->', '', tpl, flags=re.S)

    # --- 章节级文案 ---
    span = D.get('corrSpan') or ['', '', 0]
    text = {
        'TITLE':     nar.get('_title', '持仓体检报告'),
        'ASOF':      nar.get('_asof') or D.get('asof') or '',
        'SYMS':      D.get('syms', ''),
        'DIMS':      nar.get('_dims', '估值 · 基本面 · 资金 · 技术 + 组合结构'),
        'CCY':       nar.get('_ccy', D.get('ccy', '元')),
        'N':         str(D.get('n', len(S))),
        'FY':        D.get('fy', ''),
        'NQ':        str(len(nar.get('_questions', []))),
        'CORR_N':    str(span[2] if len(span) > 2 else ''),
        'CORR_SPAN': f"{span[0]} → {span[1]}" if len(span) > 1 else '',
        'IDX20':     str(D.get('index_20d', 0)),
        'HERO':      nar.get('_hero') or DEFAULT_HERO,
        'FOOTER':    nar.get('_footer', ''),
        'NOTE_S3':   nar.get('_note_s3', ''),
        'NOTE_S4':   nar.get('_note_s4', ''),
        'NOTE_S5':   nar.get('_note_s5', ''),
        'NOTE_S6':   nar.get('_note_s6', ''),
        'NOTE_S7':   nar.get('_note_s7', ''),
        'PORTFOLIO': render_portfolio(nar.get('_portfolio')),
        'STEPS':     render_steps(nar.get('_steps', [])),
        'QUESTIONS': render_questions(nar.get('_questions', [])),
        'SOURCES':   render_sources(nar.get('_sources', [])),
    }
    for _ in range(2):                     # 两遍：允许章节块文本里嵌占位符
        for k, v in text.items():
            tpl = tpl.replace('__' + k + '__', str(v))

    # --- 数据与图表 ---
    tpl = tpl.replace('__DATA__',
                      json.dumps(S, ensure_ascii=False, separators=(',', ':')))
    tpl = tpl.replace('__CORR__', json.dumps(D.get('corr') or []))
    tpl = tpl.replace('__CORRAVG__', str(D.get('corrAvg')))

    left = sorted(set(re.findall(r'__[A-Z_0-9]+__', tpl)) - {'__ECHARTS__'})

    ech = io.open(ech_p, encoding='utf-8').read()
    tpl = tpl.replace('/*__ECHARTS__*/', ech)

    io.open(out_p, 'w', encoding='utf-8').write(tpl)
    sys.stderr.write(f"OK → {out_p} ({os.path.getsize(out_p)} bytes)\n")
    sys.stderr.write(f"   排名: {[s['name'] + str(s['total']) for s in S]}\n")
    if miss:
        sys.stderr.write(f"   ⚠ 缺个股文案（仅出数据图）: {miss}\n")
    if not D.get('corr'):
        sys.stderr.write("   ⚠ 无相关矩阵：热力图空白，请把 kline.txt 传给 score.py\n")
    for k in ('_portfolio', '_steps', '_questions', '_sources'):
        if not nar.get(k):
            sys.stderr.write(f"   ⚠ narration.json 缺 {k}，对应章节将为空\n")
    if not D.get('fy'):
        sys.stderr.write("   ⚠ data.json 无 fy 字段：raw.json 里加 \"fy\":\"2025 年报\" 可自动填充口径\n")
    if left:
        sys.stderr.write(f"   ✗ 未替换占位符: {left}\n")


if __name__ == '__main__':
    main()
