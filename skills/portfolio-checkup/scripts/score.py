# -*- coding: utf-8 -*-
"""
score.py — 持仓体检四维评分引擎（通用版）

用法:
    python3 score.py raw.json [kline.txt] > data.json
    python3 score.py raw.json --sensitivity      # 只跑权重敏感性检验

raw.json 结构:
{
  "index_name": "沪深300",
  "index_20d": -5.84,
  "weights": {"qual":0.45,"flow":0.20,"val":0.20,"tech":0.15},
  "thresholds": {"keep":70,"watch":52},
  "stocks": [
    {"code":"sh600519","name":"贵州茅台","scode":"600519","ind":"白酒",
     "px":1272.75,"d1":-0.41,"d5":-2.79,"d20":-1.94,
     "pe":19.54,"pepct":5.96,"pb":6.33,"pbpct":3.23,"dy":4.08,
     "roe":32.53,"npm":50.53,"gpm":91.18,"rev_yoy":-1.21,"np_yoy":-4.53,
     "debt":16.42,"cr":5.09,"qr":3.85,"fcf":686.0,
     "ff20":-22.38,"ff5":-10.70,"ff1":-0.60,"mcap":15940,
     "ma20":1296.30,"ma60":1278.52,"ma250":1352.84,
     "rsi6":29.42,"kdj_j":1.85,"macd":-8.75,"y1":-10.41,"vol":22.1}
  ]
}

字段口径（务必按此取数，否则分数不可比）:
  d1/d5/d20/y1  %      区间涨跌幅（收盘价口径）；y1 = 近 1 年累计
  pepct/pbpct   %      PE / PB 的五年历史分位（0-100，越低越便宜）
  dy            %      近 12 个月已实施现金分红 / 最新收盘价
  roe           %      加权净资产收益率（年报口径）
  npm/gpm       %      销售净利率 / 销售毛利率
  np_yoy        %      归母净利润同比   rev_yoy % 营业收入同比
  debt          %      资产负债率      cr/qr    流动比率 / 速动比率
  fcf           亿元   自由现金流量（可为负，其余为 0 时按 0 处理）
  ff20/ff5/ff1  亿元   20 日 / 5 日 / 当日主力资金净流入（流出为负）
  mcap          亿元   总市值（用于资金维度归一）
  macd          绝对值 MACD 柱状值（DIF-DEA）
  rsi6          0-100  RSI(6)
  vol           %      年化波动率
"""
import json, re, math, sys, os
from collections import Counter

DEFAULT_WEIGHTS = {"qual": 0.45, "flow": 0.20, "val": 0.20, "tech": 0.15}


def cl(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


# --------------------------- 四维打分 ---------------------------
def score_stock(s, idx20):
    # 估值 (20%): PE 分位 45% + PB 分位 45% + 股息率 10%
    pct_part = 100 - 0.5 * s['pepct'] - 0.5 * s['pbpct']
    dy_part = cl(20 + s['dy'] * 16)
    s['val'] = round(0.90 * pct_part + 0.10 * dy_part, 1)

    # 基本面质量 (45%)
    m = {
        'roe':  cl(s['roe'] / 35 * 100),
        'npm':  cl(s['npm'] / 55 * 100),
        'gpm':  cl(s['gpm'] / 92 * 100),
        'grow': cl((s['np_yoy'] + 30) / 75 * 100),
        'debt': cl((80 - s['debt']) / 75 * 100),
        'cr':   cl(s['cr'] / 6 * 100),
        'fcf':  cl((s['fcf'] + 500) / 1200 * 100),
    }
    s['_m'] = {k: round(v) for k, v in m.items()}
    s['qual'] = round(.22 * m['roe'] + .12 * m['npm'] + .08 * m['gpm'] +
                      .25 * m['grow'] + .15 * m['debt'] + .10 * m['cr'] +
                      .08 * m['fcf'], 1)

    # 资金动向 (20%)：按市值归一，否则大小盘绝对值不可比
    o20 = -s['ff20'] / s['mcap'] * 100
    o5 = -s['ff5'] / s['mcap'] * 100
    o1 = -s['ff1'] / s['mcap'] * 100
    s['_o20'], s['_o5'], s['_o1'] = round(o20, 3), round(o5, 3), round(o1, 3)
    s['flow'] = round(.70 * cl(70 - o20 * 35) + .15 * cl(70 - o5 * 35) +
                      .15 * cl(70 - o1 * 35), 1)

    # 技术位置 (15%)
    exc = s['d20'] - idx20
    dev = s['px'] / s['ma250'] * 100 - 100
    mac = s['macd'] / s['px'] * 100
    s['exc'], s['dev'] = round(exc, 2), round(dev, 2)
    s['tech'] = round(.40 * cl((exc + 18) / 23 * 100) +
                      .30 * cl((dev + 25) / 25 * 100) +
                      .15 * cl((mac + 2.2) / 2.7 * 100) +
                      .15 * cl((s['rsi6'] - 15) / 40 * 100), 1)
    return s


def composite(s, w):
    return w['qual'] * s['qual'] + w['flow'] * s['flow'] + \
           w['val'] * s['val'] + w['tech'] * s['tech']


def verdict_of(total, th):
    if total >= th['keep']:
        return '保留'
    if total >= th['watch']:
        return '观察'
    return '减仓'


# --------------------------- 相关系数 ---------------------------
def corr_matrix(kline_path, codes):
    """从 westock kline 输出解析收盘价并算日收益率相关系数。
    注意: kline 列序为 symbol|date|open|last|high|low|volume|amount|exchange
          close 是第 4 列（索引 3），不是第 5 列。"""
    d = {}
    for line in open(kline_path, encoding='utf-8'):
        p = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(p) == 9 and re.match(r'^(sh|sz|bj|hk|us)', p[0]):
            try:
                d.setdefault(p[0], {})[p[1]] = float(p[3])
            except ValueError:
                pass
    have = [c for c in codes if c in d]
    if len(have) < 2:
        return None, None, None
    dates = sorted(set.intersection(*[set(d[c].keys()) for c in have]))
    R = {c: [d[c][dates[i]] / d[c][dates[i - 1]] - 1 for i in range(1, len(dates))]
         for c in have}

    def _c(a, b):
        n = len(a); ma = sum(a) / n; mb = sum(b) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / n
        sa = math.sqrt(sum((x - ma) ** 2 for x in a) / n)
        sb = math.sqrt(sum((y - mb) ** 2 for y in b) / n)
        return cov / (sa * sb) if sa and sb else 0.0

    M = [[round(_c(R[a], R[b]), 3) for b in have] for a in have]
    avg = round(sum(M[i][j] for i in range(len(have))
                    for j in range(len(have)) if i < j) /
                max(1, len(have) * (len(have) - 1) // 2), 3)
    return M, avg, (dates[0], dates[-1], len(dates)), have


# --------------------------- 敏感性检验 ---------------------------
def sensitivity(stocks, idx20, w0):
    """扫描基本面质量权重，看'垫底'与'次弱'如何翻转。
    这是必做步骤——权重是主观选择，必须交代结论的适用范围。"""
    ratio = {k: w0[k] for k in ('flow', 'val', 'tech')}
    tot_ratio = sum(ratio.values())
    rows, last_c, second_c = [], Counter(), Counter()
    for wq in [x / 100 for x in range(15, 105, 5)]:
        rest = 1 - wq
        w = {'qual': wq}
        for k in ratio:
            w[k] = ratio[k] / tot_ratio * rest
        r = sorted(stocks, key=lambda s: -composite(s, w))
        last_c[r[-1]['name']] += 1
        second_c[r[-2]['name']] += 1
        rows.append((wq, w, r))
    return rows, last_c, second_c


# --------------------------- main ---------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    raw = json.load(open(sys.argv[1], encoding='utf-8'))
    kw = raw.get('weights') or DEFAULT_WEIGHTS
    w = {k: kw.get(k, DEFAULT_WEIGHTS[k]) for k in DEFAULT_WEIGHTS}
    idx20 = raw.get('index_20d', -5.84)
    idx_name = raw.get('index_name', '沪深300')
    th = raw.get('thresholds') or {'keep': 70, 'watch': 52}
    stocks = [score_stock(dict(s), idx20) for s in raw['stocks']]

    for s in stocks:
        s['_total_raw'] = composite(s, w)
        s['total'] = round(s['_total_raw'], 1)
        s['verdict'] = verdict_of(s['total'], th)
        s.pop('_total_raw', None)

    codes = [s['code'] for s in stocks]
    C = None
    kl = None
    for a in sys.argv[2:]:
        if a.endswith('.txt') and os.path.exists(a):
            kl = a
    if kl:
        C = corr_matrix(kl, codes)

    stocks.sort(key=lambda x: -x['total'])
    if C:
        M, avg, span, have = C
        idx = [have.index(s['code']) for s in stocks if s['code'] in have]
        M2 = [[M[i][j] for j in idx] for i in idx]
    else:
        M2, avg, span = None, None, None

    out = {'stocks': stocks, 'corr': M2, 'corrAvg': avg, 'corrSpan': span,
           'index_name': idx_name, 'index_20d': idx20, 'weights': w,
           'thresholds': th,
           # 以下派生字段供 build.py 自动填充模板占位符，无需人工填写
           'n': len(stocks),
           'syms': ' / '.join(s['name'] for s in stocks),
           'asof': raw.get('asof', ''),
           'fy': raw.get('fy', ''),
           'ccy': raw.get('ccy', '元')}

    if '--sensitivity' in sys.argv:
        rows, lc, sc = sensitivity(stocks, idx20, w)
        print(f"■ 权重敏感性检验（基本面质量权重扫描，其余三维等比分配）")
        print(f"{'质量':>5}{'资金':>7}{'估值':>7}{'技术':>7}   垫底        次弱")
        print('-' * 62)
        for wq, ww, r in rows:
            print(f"{wq:>5.2f}{ww['flow']:>7.2f}{ww['val']:>7.2f}{ww['tech']:>7.2f}"
                  f"   {r[-1]['name']:<11}{r[-2]['name']}")
        print(f"\n■ 垫底出现次数:   " +
              '  '.join(f'{k}×{v}' for k, v in lc.most_common()))
        print(f"■ 次弱出现次数:   " +
              '  '.join(f'{k}×{v}' for k, v in sc.most_common()))
        print("\n把'次弱次数最多'的那只写进报告的稳健性提示——它比'垫底'更不依赖权重假设。")
        return

    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    sys.stderr.write(f"OK 排名={[s['name'] + str(s['total']) for s in stocks]}\n")
    if avg is not None:
        sys.stderr.write(f"   平均两两相关={avg} 窗口={span}\n")


if __name__ == '__main__':
    main()
