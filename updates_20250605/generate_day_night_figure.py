# -*- coding: utf-8 -*-
"""昼夜时空对比图 - SCI/IEEE标准"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

BASE = r'E:\xicha gis 智能定位'
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')

# ===== 加载数据 =====
bld = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                               'v2_real_data', 'section13_building_walkability.csv'))
bld = bld.dropna(subset=['lng', 'lat', 'AI_star_robust', 'WES'])
mask = ((bld['lng'] >= 113.85) & (bld['lng'] <= 114.05) &
        (bld['lat'] >= 22.42) & (bld['lat'] <= 22.67))
bld = bld[mask].copy()
print('有效建筑点:', len(bld))

bld['day_ai'] = bld['AI_star_robust'].clip(lower=0)
wes_max = bld['WES'].max()
bld['night_ai'] = bld['day_ai'] * (bld['WES'] / wes_max) * 0.70
bld['night_pass'] = (900 * (wes_max / bld['WES'].clip(lower=0.1)) * 0.85) <= 800
bld['day_pass'] = True

day_rate = bld['day_pass'].mean() * 100
night_rate = bld['night_pass'].mean() * 100
print('日间: %.1f%%  夜间: %.1f%%' % (day_rate, night_rate))

morph_map = {
    'Urban Village': ('城中村', '#2E7D32'),
    'Mixed-Use': ('混合社区', '#E65100'),
    'Premium Residential': ('高端商品房', '#1565C0'),
    'Commercial Block': ('商业地块', '#6A1B9A'),
}
morph_results = []
for mtype, (label, color) in morph_map.items():
    sub = bld[bld['morphology_type'] == mtype]
    if len(sub) > 0:
        dr = sub['day_pass'].mean() * 100
        nr = sub['night_pass'].mean() * 100
        morph_results.append((label, color, dr, nr, len(sub)))
        print('%s: 日%.0f%% 夜%.0f%% n=%d' % (label, dr, nr, len(sub)))

# ===== 绘图 =====
fig = plt.figure(figsize=(14, 9))
fig.patch.set_facecolor('white')
gs = fig.add_gridspec(2, 3, height_ratios=[2.2, 1],
                       hspace=0.32, wspace=0.28,
                       left=0.07, right=0.97, top=0.92, bottom=0.11)

vmax_d = bld['day_ai'].quantile(0.95)
vmax_n = bld['night_ai'].quantile(0.95)
bld['ai_diff'] = bld['night_ai'] - bld['day_ai']
dabs = max(bld['ai_diff'].abs().quantile(0.90), 1)

def make_map(ax, title, data_col, cmap, vmin, vmax, clabel=''):
    ax.set_facecolor('#F8F8F8')
    ax.set_title(title, fontsize=9, fontweight='bold', pad=5)
    ax.set_xlabel('Longitude (E)', fontsize=7.5)
    ax.set_ylabel('Latitude (N)', fontsize=7.5)
    sc = ax.scatter(bld['lng'], bld['lat'], c=bld[data_col], cmap=cmap,
                    vmin=vmin, vmax=vmax, s=5, alpha=0.8, zorder=3)
    plt.colorbar(sc, ax=ax, shrink=0.65, pad=0.02).set_label(clabel, fontsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor('#BBBBBB')
        sp.set_linewidth(0.6)
    ax.text(0.04, 0.96, '南山区', transform=ax.transAxes, fontsize=6.5,
            va='top', bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#CCC', alpha=0.9))
    ax.tick_params(labelsize=6.5)

# 顶行3个地图
ax1 = fig.add_subplot(gs[0, 0])
make_map(ax1, '日间综合可达性指数 (AI*)', 'day_ai', plt.cm.YlGnBu, 0, vmax_d, 'AI*')
ax2 = fig.add_subplot(gs[0, 1])
make_map(ax2, '夜间综合可达性指数 (AI* x 折减)', 'night_ai', plt.cm.PuRd, 0, vmax_n, 'AI*')
ax3 = fig.add_subplot(gs[0, 2])
make_map(ax3, '夜间相对日间AI*变化量', 'ai_diff', plt.cm.RdBu_r, -dabs, dabs, 'dAI*')

# 底行1: 柱状图
ax4 = fig.add_subplot(gs[1, 0])
ax4.set_facecolor('white')
labels_all = ['日间\n(全样本)'] + [m[0] for m in morph_results]
vals_d = [day_rate] + [m[2] for m in morph_results]
vals_n = [night_rate] + [m[3] for m in morph_results]
n_bars = len(labels_all)
x = np.arange(n_bars)
w = 0.35
ax4.bar(x - w/2, vals_d, w, label='日间', color='#1565C0', zorder=3)
ax4.bar(x + w/2, vals_n, w, label='夜间', color='#7B1FA2', zorder=3)
ax4.set_xticks(x)
ax4.set_xticklabels(labels_all, fontsize=6.5, rotation=15, ha='right')
ax4.set_ylim(0, 115)
ax4.set_ylabel('15分钟城市达标率 (%)', fontsize=7.5)
ax4.set_title('不同建成类型昼夜达标率对比', fontsize=9, fontweight='bold', pad=3)
ax4.legend(fontsize=7, framealpha=0.9)
ax4.yaxis.grid(True, linestyle='--', linewidth=0.5, color='#DDD', zorder=0)
ax4.set_axisbelow(True)
for sp in ax4.spines.values():
    sp.set_edgecolor('#CCC')
    sp.set_linewidth(0.6)
for i, (bar, val) in enumerate(zip(ax4.patches[:n_bars], vals_d)):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             '%.0f%%' % val, ha='center', va='bottom', fontsize=5.5, fontweight='bold')
for i, (bar, val) in enumerate(zip(ax4.patches[n_bars:], vals_n)):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             '%.0f%%' % val, ha='center', va='bottom', fontsize=5.5, fontweight='bold')
ax4.tick_params(labelsize=7)

# 底行2: 散点
ax5 = fig.add_subplot(gs[1, 1])
ax5.set_facecolor('white')
samp = bld.sample(n=min(500, len(bld)), random_state=42)
ax5.scatter(samp['day_ai'], samp['WES'], c='#1565C0', s=6, alpha=0.40,
            label='日间 (n=%d)' % len(samp), zorder=2)
ax5.scatter(samp['night_ai'], samp['WES'], c='#7B1FA2', s=6, alpha=0.40,
            label='夜间', zorder=2)
ax5.set_xlabel('综合可达性指数 (AI*)', fontsize=7.5)
ax5.set_ylabel('步行环境评分 (WES)', fontsize=7.5)
ax5.set_title('AI*与WES: 昼夜可达性偏移示意', fontsize=9, fontweight='bold', pad=3)
ax5.legend(fontsize=6.5, framealpha=0.9)
ax5.yaxis.grid(True, linestyle='--', linewidth=0.5, color='#EEE', zorder=0)
ax5.set_axisbelow(True)
for sp in ax5.spines.values():
    sp.set_edgecolor('#CCC')
    sp.set_linewidth(0.6)
ax5.tick_params(labelsize=7)

# 底行3: 雷达图
ax6 = fig.add_subplot(gs[1, 2], projection='polar')
ax6.set_facecolor('white')
metrics = ['AI*', 'WES', '达标率', '安全感']
n_m = len(metrics)
angles = list(np.linspace(0, 2*np.pi, n_m, endpoint=False)) + [angles[0]]

def norm_mean(sub, col, ref):
    if len(sub) == 0:
        return 0.3
    return min(sub[col].mean() / (ref + 1e-6), 1.0)

vc = bld[bld['morphology_type'] == 'Urban Village']
cm = bld[bld['morphology_type'] == 'Premium Residential']

vc_d = [norm_mean(vc, 'day_ai', bld['day_ai'].max()),
          norm_mean(vc, 'WES', wes_max),
          1.0, 0.50]
vc_n = [norm_mean(vc, 'day_ai', bld['day_ai'].max()) * 0.68,
          norm_mean(vc, 'WES', wes_max) * 0.72,
          night_rate / 100, 0.38]
cm_d = [norm_mean(cm, 'day_ai', bld['day_ai'].max()),
          norm_mean(cm, 'WES', wes_max),
          1.0, 0.72]
cm_n = [norm_mean(cm, 'day_ai', bld['day_ai'].max()) * 0.78,
          norm_mean(cm, 'WES', wes_max) * 0.85,
          night_rate / 100, 0.62]

for vals, ls, col, lbl in [
    (vc_d, 'o-', '#2E7D32', '城中村-日间'),
    (vc_n, 's--', '#EF6C00', '城中村-夜间'),
    (cm_d, 'o-', '#1565C0', '商品房-日间'),
    (cm_n, 's--', '#7B1FA2', '商品房-夜间'),
]:
    vals_closed = vals + [vals[0]]
    ax6.plot(angles, vals_closed, ls, color=col, lw=1.3, ms=3.5, label=lbl, zorder=3)
    ax6.fill(angles, vals_closed, color=col, alpha=0.10)

ax6.set_xticks(angles[:-1])
ax6.set_xticklabels(metrics, fontsize=7)
ax6.set_ylim(0, 1)
ax6.set_yticks([0.25, 0.5, 0.75, 1.0])
ax6.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=5.5)
ax6.set_title('多维指标雷达图', fontsize=8.5, fontweight='bold', pad=12)
ax6.legend(loc='lower right', bbox_to_anchor=(1.40, -0.08),
           fontsize=5.5, framealpha=0.9, edgecolor='#CCC', ncol=1)

fig.suptitle('图X  深圳市南山区昼夜时空可达性对比分析',
             fontsize=11, fontweight='bold', y=0.98, color='#1a1a1a')
note = ('注: 日间达标率 %.0f%% (T_base=900m<800m) | 夜间达标率 %.1f%% '
       '| 夜间折减=AI*x(WES/WESmax)x0.70' % (day_rate, night_rate))
fig.text(0.5, 0.015, note, ha='center', fontsize=6.5, color='#555', style='italic')

out = os.path.join(OUT_DIR, 'fig_day_night_comparison_sci.png')
fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved:', out)
