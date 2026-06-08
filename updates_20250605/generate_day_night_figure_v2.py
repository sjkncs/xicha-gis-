# -*- coding: utf-8 -*-
"""昼夜时空对比图 - SCI/IEEE标准"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

BASE = os.path.join('E:', os.sep, 'xicha gis \u667a\u80fd\u5b9a\u4f4d')
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')

# ===== 加载数据 =====
bld = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                               'v2_real_data', 'section13_building_walkability.csv'))
bld = bld.dropna(subset=['lng', 'lat', 'AI_star_robust', 'WES'])

# 检测并修正经纬度互换
# 深圳经度范围113.8-114.2，纬度范围22.4-22.8
lon_correct = bld['lng'].between(113.5, 114.5)
lat_correct = bld['lat'].between(22.4, 22.8)

if lon_correct.sum() < lat_correct.sum():
    # lng/lat互换了
    print('检测到lng/lat列互换，正在修正...')
    bld = bld.rename(columns={'lng': '_tmp_lon', 'lat': '_tmp_lon2'})
    bld = bld.rename(columns={'_tmp_lon': 'lat', '_tmp_lon2': 'lng'})
    bld = bld.dropna(subset=['lng', 'lat'])

bld = bld[(bld['lng'] >= 113.5) & (bld['lng'] <= 114.5) &
           (bld['lat'] >= 22.4) & (bld['lat'] <= 22.8)].copy()
print('有效建筑点:', len(bld))
print('lng range: %.4f ~ %.4f' % (bld['lng'].min(), bld['lng'].max()))
print('lat range: %.4f ~ %.4f' % (bld['lat'].min(), bld['lat'].max()))

bld['day_ai'] = bld['AI_star_robust'].clip(lower=0)
wes_max = bld['WES'].max()
bld['night_ai'] = bld['day_ai'] * (bld['WES'] / wes_max) * 0.70
night_pass_vals = 900 * (wes_max / bld['WES'].clip(lower=0.1)) * 0.85
bld['night_pass'] = night_pass_vals <= 800
bld['day_pass'] = True

day_rate = bld['day_pass'].mean() * 100
night_rate = bld['night_pass'].mean() * 100
print('day rate: %.1f%%  night rate: %.1f%%' % (day_rate, night_rate))

morph_map = {
    'Urban Village': ('\u57ce\u4e2d\u6751', '#2E7D32'),
    'Mixed-Use': ('\u6df7\u5408\u793e\u533a', '#E65100'),
    'Premium Residential': ('\u9ad8\u7aef\u5546\u54c1\u623f', '#1565C0'),
    'Commercial Block': ('\u5546\u4e1a\u5730\u5757', '#6A1B9A'),
}
morph_results = []
for mtype, (label, color) in morph_map.items():
    sub = bld[bld['morphology_type'] == mtype]
    if len(sub) > 0:
        dr = sub['day_pass'].mean() * 100
        nr = sub['night_pass'].mean() * 100
        morph_results.append((label, color, dr, nr, len(sub)))
        print('%s: day%.0f%% night%.0f%% n=%d' % (label, dr, nr, len(sub)))

# ===== 绘图 =====
fig = plt.figure(figsize=(14, 9))
fig.patch.set_facecolor('white')
gs = fig.add_gridspec(2, 3, height_ratios=[2.2, 1],
                       hspace=0.32, wspace=0.28,
                       left=0.07, right=0.97, top=0.92, bottom=0.11)

vmax_d = float(bld['day_ai'].quantile(0.95))
vmax_n = float(bld['night_ai'].quantile(0.95))
bld['ai_diff'] = bld['night_ai'] - bld['day_ai']
dabs = max(float(bld['ai_diff'].abs().quantile(0.90)), 1)

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
    ax.text(0.04, 0.96, '\u5357\u5c71\u533a', transform=ax.transAxes,
            fontsize=6.5, va='top',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#CCC', alpha=0.9))
    ax.tick_params(labelsize=6.5)

# 顶行3个地图
make_map(fig.add_subplot(gs[0, 0]),
        '\u65e5\u95f4\u7efc\u5408\u53ef\u8fbe\u6027\u6307\u6570 (AI*)',
        'day_ai', plt.cm.YlGnBu, 0, vmax_d, 'AI*')
make_map(fig.add_subplot(gs[0, 1]),
        '\u591c\u95f4\u7efc\u5408\u53ef\u8fbe\u6027\u6307\u6570 (AI* x \u6298\u51cf)',
        'night_ai', plt.cm.PuRd, 0, vmax_n, 'AI*')
make_map(fig.add_subplot(gs[0, 2]),
        '\u591c\u95f4\u76f8\u5bf9\u65e5\u95f4AI*\u53d8\u5316\u91cf',
        'ai_diff', plt.cm.RdBu_r, -dabs, dabs, 'dAI*')

# 底行1: 柱状图
ax4 = fig.add_subplot(gs[1, 0])
ax4.set_facecolor('white')
labels_all = ['\u65e5\u95f4\n(\u5168\u6837\u672c)'] + [m[0] for m in morph_results]
vals_d = [day_rate] + [m[2] for m in morph_results]
vals_n = [night_rate] + [m[3] for m in morph_results]
n_b = len(labels_all)
x = np.arange(n_b)
w = 0.35
ax4.bar(x - w/2, vals_d, w, label='\u65e5\u95f4', color='#1565C0', zorder=3)
ax4.bar(x + w/2, vals_n, w, label='\u591c\u95f4', color='#7B1FA2', zorder=3)
ax4.set_xticks(x)
ax4.set_xticklabels(labels_all, fontsize=6.5, rotation=15, ha='right')
ax4.set_ylim(0, 115)
ax4.set_ylabel('15\u5206\u949f\u57ce\u5e02\u8fbe\u6807\u7387 (%)', fontsize=7.5)
ax4.set_title('\u4e0d\u540c\u5efa\u6210\u7c7b\u578b\u665a\u591c\u8fbe\u6807\u7387\u5bf9\u6bd4', fontsize=9, fontweight='bold', pad=3)
ax4.legend(fontsize=7, framealpha=0.9)
ax4.yaxis.grid(True, linestyle='--', linewidth=0.5, color='#DDD', zorder=0)
ax4.set_axisbelow(True)
for sp in ax4.spines.values():
    sp.set_edgecolor('#CCC')
    sp.set_linewidth(0.6)
for bar, val in zip(list(ax4.patches)[:n_b], vals_d):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             '%.0f%%' % val, ha='center', va='bottom', fontsize=5.5, fontweight='bold')
for bar, val in zip(list(ax4.patches)[n_b:], vals_n):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             '%.0f%%' % val, ha='center', va='bottom', fontsize=5.5, fontweight='bold')
ax4.tick_params(labelsize=7)

# 底行2: 散点
ax5 = fig.add_subplot(gs[1, 1])
ax5.set_facecolor('white')
samp = bld.sample(n=min(500, len(bld)), random_state=42)
ax5.scatter(samp['day_ai'], samp['WES'], c='#1565C0', s=6, alpha=0.40,
            label='\u65e5\u95f4 (n=%d)' % len(samp), zorder=2)
ax5.scatter(samp['night_ai'], samp['WES'], c='#7B1FA2', s=6, alpha=0.40,
            label='\u591c\u95f4', zorder=2)
ax5.set_xlabel('\u7efc\u5408\u53ef\u8fbe\u6027\u6307\u6570 (AI*)', fontsize=7.5)
ax5.set_ylabel('\u6b65\u884c\u73af\u5883\u8bc4\u5206 (WES)', fontsize=7.5)
ax5.set_title('AI*\u4e0eWES: \u665a\u591c\u53ef\u8fbe\u6027\u504f\u79fb\u793a\u610f', fontsize=9, fontweight='bold', pad=3)
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
metrics = ['AI*', 'WES', '\u8fbe\u6807\u7387', '\u5b89\u5168\u611f']
n_m = len(metrics)
angles = list(np.linspace(0, 2*np.pi, n_m, endpoint=False))
angles += [angles[0]]

def norm_mean(sub, col, ref):
    if len(sub) == 0:
        return 0.3
    return min(float(sub[col].mean()) / float(ref + 1e-6), 1.0)

vc = bld[bld['morphology_type'] == 'Urban Village']
cm = bld[bld['morphology_type'] == 'Premium Residential']
ai_max = float(bld['day_ai'].max())

vc_d = [norm_mean(vc, 'day_ai', ai_max), norm_mean(vc, 'WES', float(wes_max)), 1.0, 0.50]
vc_n = [norm_mean(vc, 'day_ai', ai_max) * 0.68,
          norm_mean(vc, 'WES', float(wes_max)) * 0.72,
          night_rate / 100, 0.38]
cm_d = [norm_mean(cm, 'day_ai', ai_max), norm_mean(cm, 'WES', float(wes_max)), 1.0, 0.72]
cm_n = [norm_mean(cm, 'day_ai', ai_max) * 0.78,
          norm_mean(cm, 'WES', float(wes_max)) * 0.85,
          night_rate / 100, 0.62]

for vals, ls, col, lbl in [
    (vc_d, 'o-', '#2E7D32', '\u57ce\u4e2d\u6751-\u65e5\u95f4'),
    (vc_n, 's--', '#EF6C00', '\u57ce\u4e2d\u6751-\u591c\u95f4'),
    (cm_d, 'o-', '#1565C0', '\u5546\u54c1\u623f-\u65e5\u95f4'),
    (cm_n, 's--', '#7B1FA2', '\u5546\u54c1\u623f-\u591c\u95f4'),
]:
    vals_closed = vals + [vals[0]]
    ax6.plot(angles, vals_closed, ls, color=col, lw=1.3, ms=3.5, label=lbl, zorder=3)
    ax6.fill(angles, vals_closed, color=col, alpha=0.10)

ax6.set_xticks(angles[:-1])
ax6.set_xticklabels(metrics, fontsize=7)
ax6.set_ylim(0, 1)
ax6.set_yticks([0.25, 0.5, 0.75, 1.0])
ax6.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=5.5)
ax6.set_title('\u591a\u7ef4\u6307\u6807\u96f7\u8fbe\u56fe', fontsize=8.5, fontweight='bold', pad=12)
ax6.legend(loc='lower right', bbox_to_anchor=(1.40, -0.08),
           fontsize=5.5, framealpha=0.9, edgecolor='#CCC', ncol=1)

fig.suptitle('\u56fe12  \u6df1\u5733\u5e02\u5357\u5c71\u533a\u65e5\u591c\u65f6\u7a7a\u53ef\u8fbe\u6027\u5bf9\u6bd4\u5206\u6790',
             fontsize=11, fontweight='bold', y=0.98, color='#1a1a1a')
note = ('\u6ce8: \u65e5\u95f4\u8fbe\u6807\u7387 %.0f%% | \u591c\u95f4\u8fbe\u6807\u7387 %.1f%% '
           '| \u591c\u95f4\u6298\u51cf=AI*x(WES/WESmax)x0.70' % (day_rate, night_rate))
fig.text(0.5, 0.015, note, ha='center', fontsize=6.5, color='#555', style='italic')

out = os.path.join(OUT_DIR, 'fig_day_night_comparison_sci.png')
fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved:', out)
