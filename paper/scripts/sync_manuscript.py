"""Refresh Chinese result tables from the same pinned snapshot as the English figures."""
import argparse
import itertools
import json
from pathlib import Path
from statistics import median

import numpy as np

from paper_snapshot import load_snapshot

PAPER = Path(__file__).resolve().parents[1]


def table(header, rows):
    return '\n'.join(['| ' + ' | '.join(header) + ' |',
                      '|' + '|'.join(['---'] * len(header)) + '|'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def replace_table(text, section, value):
    start = text.index('\n|', text.index(section)) + 1
    end = text.index('\n\n', start)
    return text[:start] + value + text[end:]


def render(text, data):
    seeds = data['seeds']
    widths = {(r['seed'], r['subset']): r['width68'] for r in data['records']}
    auc = {(r['seed'], r['subset']): r['auc'] for r in data['records']}
    order = sorted(data['subsets'][1:], key=lambda s: median(widths[k,s] for k in seeds)) + ['']
    rows = []
    for subset in order:
        vals = [widths[k,subset] for k in seeds]
        rows.append([subset or 'M0off（空集）', sum(dict(A=8,B=4,C=2,D=5)[g] for g in subset),
                     f'{median(vals):.6f}', f'{min(vals):.6f}–{max(vals):.6f}',
                     f'{100*median(1-widths[k,subset]/widths[k,""] for k in seeds):.3f}%',
                     f'{median(auc[k,subset] for k in seeds):.6f}' if subset else '—'])
    text = replace_table(text, '### 5.1', table(['组合','输入数','W68 中位数','五种子最小–最大','相对空集改善','验证 AUC 中位数'],rows))
    rows = []
    for left,right in [('AC','BC'),('AC','ABCD'),('BC','ABCD'),('ABC','ABCD')]:
        pair = next(r for r in data['pairwise'] if r['left']==left and r['right']==right)
        gain = pair['relative_improvement_left_vs_right']
        lo,hi = gain['interval95']
        rows.append([f'{left} / {right}', f'{pair["delta_width68_left_minus_right"]["median"]:+.6f}',
                     f'{100*gain["median"]:+.3f}%', f'[{100*lo:+.3f}%, {100*hi:+.3f}%]',
                     f'{pair["strict_win_count"]}/5'])
    text = replace_table(text,'### 5.2',table(['比较（左／右）','配对 ΔW68 中位数','配对相对改善中位数','95% 种子稳定性区间（改善）','左侧胜出种子数'],rows))
    rows = []
    for r in data['attribution']:
        # Exhaustive registered five-seed resampling, aggregate algebra only.
        medians = [median(r['per_seed'][i] for i in draw) for draw in itertools.product(range(5), repeat=5)]
        lo,hi = np.quantile(medians,[.025,.975],method='linear')
        rows.append([r['group'],f'{r["median"]:+.6f}',f'[{lo:+.6f}, {hi:+.6f}]'])
    text = replace_table(text,'### 5.3',table(['组','Shapley 中位数','95% 训练种子稳定性区间'],rows))
    rows = []
    for stage,mu in [('assessment',0),('assessment',1),('assessment',2),('t2',1)]:
        for subset in ('','BC','AC','ABCD'):
            values = []
            for level in (.68,.95):
                r = next(r for r in data['diagnostics'] if r['stage']==stage and float(r['mu'])==mu
                         and r['subset']==subset and float(r['confidence_level'])==level and r['metric']=='conditional_coverage')
                values.append(f'{float(r["median"]):.4f}' if r['status']=='valid' and r['median'] else '—')
            rows.append([stage,mu,subset or 'M0off',*values])
    text = replace_table(text,'### 5.4',table(['母模板／层次','注入 μ','组合','68% 覆盖率中位数','95% 覆盖率中位数'],rows))
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if tables drift; do not write.')
    args = parser.parse_args()
    path = PAPER/'manuscript.md'
    old = path.read_text(encoding='utf-8')
    new = render(old, load_snapshot())
    if args.check:
        if new != old:
            raise SystemExit('Chinese manuscript tables differ from selected snapshot')
    else:
        path.write_text(new, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
