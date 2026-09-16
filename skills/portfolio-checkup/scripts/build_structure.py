# -*- coding: utf-8 -*-
"""
build_structure.py — 结构模式构建器：组合层面看暴露（集中度／杠杆／多币种）

用法:
    python3 build_structure.py payload.json references/template-structure.html \
        assets/echarts.min.js out.html

payload.json 分两段：`_text`（文本占位符）与 `_data`（注入 JS 的数据对象）。

_text:
  TITLE        报告标题（同时用于 <title> 与 <h1>）
  ACCOUNT      账户号
  ASOF         数据时点
  TODAY        报告日期
  HERO         Hero 区总结段（支持 HTML）
  CCY_SYM      计价货币符号，默认 "$"（同时注入 _data.baseCcySym）
  FX_NOTE      01 节 lede，例："美元计价口径。港币持仓已按 7.8474 折算为美元。"
  P30_RANGE    区间收益的时间范围，例："2026-08-16 → 09-14（30 个交易日）"
  POS_LEDE     02 节 lede，例："市值与盈亏已统一折算为美元；成本为券商记录的持仓均价。"
  PE_NOTE      02 节表下注释（PE 缺失说明等）
  EXP_LEDE     03 节 lede（写通用描述，不要写死具体杠杆标的名）
  EXP_LEGEND   03 节图例；省略则按 _data.exposure.groups 自动渲染
  EXPOSURE_NOTE 03 节读图
  LEV_TITLE    04 节标题（杠杆专项，含标的名，如 "TQQQ 专项：杠杆叠加与衰减"）
  LEV_NOTE     04 节图例说明
  LEV_READING  04 节读图
  VAL_NOTE     05 节读图
  ATTRIB_NOTE  06 节读图
  CROSS_TITLE  08 节标题
  CROSS_LEDE   08 节 lede
  GAPS         数据缺口段（红色框内容）
  DISCLAIMER   免责声明段（黄色框整段，含 "<b>免责声明：</b>" 前缀）
  FOOTER       页脚
  SOURCES      由 _data.sources 自动渲染，无需手填

_data:
  baseCcySym   计价货币符号（不填则取 _text.CCY_SYM 或 "$"）
  account {netliq, gross, cash, upl, upl_pct, p30d, ann, mdd}
  positions [{sym,name,ccy,qty,cost,px,mv_local,mv,w,ret,upl,r20,pe,pe_pct}]
  exposure {segs:[{name,val,group,color,first,last}],
            groups:[{name,color}],      # 堆叠顺序 = 数组顺序，用于图例与 JS
            total, leverage}
  tqqq {decay:{index_name, levName, levMult, windows:[{label,idx,theory,actual}]}}
  valuation [{name,pe,lo,hi,pe_pct,fy,fy_pe}]        # pe 为 null 的标的会被 JS 过滤
  details   [{name,sym,ind,px,ccy,w,ret,tag,tagcls,rows:[{lb,tx}],call,callcls}]
  steps     [{cls,ttl,tx}]                            # cls: c1绿 | c2橙 | c3蓝
  cross     [{title,items:[{text,cls}]}]              # 08 节卡片；cls: risk | warn | 空
  sources   [{text}]                                  # 10 节 bullet，支持 HTML

缺任何一个 _data 块，对应章节会渲染为空——构建脚本会在 stderr 逐条报警。
"""
import json, io, re, sys, os


def render_cross(cards):
    """08 跨账户叠加：卡片 + 要点列表"""
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


def render_sources(src):
    return '\n'.join(f'        <li>{s.get("text", "")}</li>' for s in src)


def render_exp_legend(groups):
    """03 节图例：按分组取色"""
    return '\n'.join(
        f'        <span><i style="background:{g.get("color", "#888")}"></i>'
        f'{g.get("name", "")}</span>' for g in groups)


REQUIRED_TEXT = ('EXP_LEDE', 'EXPOSURE_NOTE', 'LEV_TITLE', 'LEV_NOTE', 'VAL_NOTE',
                 'ATTRIB_NOTE', 'LEV_READING', 'CROSS_TITLE', 'CROSS_LEDE', 'GAPS',
                 'DISCLAIMER', 'FOOTER', 'PE_NOTE', 'POS_LEDE', 'FX_NOTE',
                 'P30_RANGE')
REQUIRED_DATA = ('account', 'positions', 'exposure', 'details', 'steps',
                 'cross', 'sources')


def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(1)
    payload_p, tpl_p, ech_p, out_p = sys.argv[1:5]

    P = json.load(open(payload_p, encoding='utf-8'))
    text = dict(P.get('_text', {}))
    data = dict(P.get('_data', {}))

    # --- 自动派生，减少手填 ---
    ccy_sym = text.get('CCY_SYM', '$')
    text['CCY_SYM'] = ccy_sym
    data.setdefault('baseCcySym', ccy_sym)

    groups = (data.get('exposure') or {}).get('groups') or []
    if not text.get('EXP_LEGEND') and groups:
        text['EXP_LEGEND'] = render_exp_legend(groups)

    text['SOURCES'] = render_sources(data.get('sources') or [])
    text['CROSS'] = render_cross(data.get('cross') or [])

    tpl = io.open(tpl_p, encoding='utf-8').read()

    for _ in range(2):                     # 两遍：允许 _data 块的文本里嵌占位符
        for k, v in text.items():
            tpl = tpl.replace('__' + k + '__', str(v))
    tpl = tpl.replace('__DATA__',
                      json.dumps(data, ensure_ascii=False, separators=(',', ':')))

    left = sorted(set(re.findall(r'__[A-Z_0-9]+__', tpl)) - {'__ECHARTS__'})
    for k in left:
        tpl = tpl.replace(k, '')

    ech = io.open(ech_p, encoding='utf-8').read()
    tpl = tpl.replace('/*__ECHARTS__*/', ech)

    io.open(out_p, 'w', encoding='utf-8').write(tpl)

    # --- 完整性检查：任何一条报警都不应交付 ---
    sys.stderr.write(f"OK → {out_p} ({os.path.getsize(out_p)} bytes)\n")
    for k in ('TITLE', 'HERO', 'ACCOUNT', 'ASOF', 'TODAY'):
        if not text.get(k):
            sys.stderr.write(f"   ⚠ _text 缺 {k}\n")
    for k in REQUIRED_DATA:
        if not data.get(k):
            sys.stderr.write(f"   ⚠ _data 缺 {k}（对应章节将为空）\n")
    miss_text = [k for k in REQUIRED_TEXT if k not in text]
    if miss_text:
        sys.stderr.write(f"   ⚠ _text 未提供: {miss_text}\n")
    if not (data.get('exposure') or {}).get('groups'):
        sys.stderr.write("   ⚠ exposure.groups 缺失：敞口堆叠图与图例会空白\n")
    if not (data.get('exposure') or {}).get('segs'):
        sys.stderr.write("   ⚠ exposure.segs 缺失：敞口图无数据\n")
    if left:
        sys.stderr.write(f"   ✗ 未替换占位符: {left}\n")


if __name__ == '__main__':
    main()
