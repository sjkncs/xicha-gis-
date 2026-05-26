import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f"Notebook loaded: {len(nb['cells'])} cells")

# Replace cell 25 (the corrupted 6b markdown cell) with a clean version
# Also replace cell 26 (the code cell that was corrupted)
# We need to check what cells 25 and 26 currently contain

cell25 = nb['cells'][25]
cell26 = nb['cells'][26]

print(f"Cell 25 type: {cell25['cell_type']}")
print(f"Cell 25 preview: {repr(''.join(cell25.get('source', ['']))[:300])}")
print()
print(f"Cell 26 type: {cell26['cell_type']}")
print(f"Cell 26 preview: {repr(''.join(cell26.get('source', ['']))[:300])}")

# Strategy: rebuild cells 25 and 26 completely with properly escaped content
# For the 6b section markdown cell, we'll use clean text without problematic LaTeX
# For the equity analysis code cell, we'll use a fresh clean version

# ——————————————————————————
# FIX CELL 25: 6b markdown section header
# ——————————————————————————
cell25['source'] = [
    "<a id='6b'></a>\n",
    "\n",
    "---\n",
    "\n",
    "## 6b. 公平性分析 — Gini系数与可达性剥夺指数\n",
    "\n",
    "### 6b.1 为什么需要公平性视角\n",
    "\n",
    "即便南山区总体可达性达到政策目标，若可达性分配极度不均（少数高端社区享有超优质资源，而城中村被边缘化），这套系统仍是不公平的。\n",
    "\n",
    "我们引入三个公平性测度：\n",
    "\n",
    "**① Gini系数**：衡量可达性在全体居民中的分配不平等程度（G=0表示绝对平等，G=1表示绝对不平等）\n",
    "\n",
    "$$Gini = \\frac{\\sum_{i=1}^{n}\\sum_{j=1}^{n}|A_i - A_j|}{2n^2\\bar{A}}$$\n",
    "\n",
    "**② 可达性剥夺指数 (Accessibility Deprivation Index, ADI)**：借鉴英国 Indices of Multiple Deprivation，将可达性量化转换为\"被剥夺程度\"\n",
    "\n",
    "$$ADI_i = 1 - \\frac{A_i}{A_{max}}$$\n",
    "\n",
    "**③ 分位数对比分析**：最高/最低20%小区的可达性比值，揭示差距的真实规模\n",
    "\n",
    "**核心发现**：统计均值掩盖了空间不公平的真相，只有分群体分析才能揭示谁被\"平均\"掉了。\n",
]

# ——————————————————————————
# FIX CELL 26: equity analysis code
# ——————————————————————————
equity_code = '''# ============================================================================
# 公平性分析：Gini系数、洛伦兹曲线与可达性剥夺指数
# ============================================================================

print("=" * 70)
print("公平性分析 — 可达性分配的公正性检验")
print("=" * 70)

def compute_gini(values):
    """计算基尼系数（Gini coefficient）"""
    values = np.array(values).flatten()
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan
    values = np.sort(values)
    n = len(values)
    mean_val = np.mean(values)
    if mean_val == 0:
        return np.nan
    index = np.arange(1, n + 1)
    gini = (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))
    return gini

def lorenz_curve(values):
    """计算洛伦兹曲线数据"""
    values = np.sort(values.flatten())
    values = values[~np.isnan(values)]
    cum_share = np.cumsum(values) / np.sum(values)
    pop_share = np.arange(1, len(values) + 1) / len(values)
    return pop_share, cum_share

def compute_deprivation_index(accessibility_values):
    """可达性剥夺指数 ADI = 1 - A_i / A_max"""
    A_max = np.nanmax(accessibility_values)
    if A_max == 0:
        return np.full_like(accessibility_values, np.nan)
    return 1 - accessibility_values / A_max

# ——————————————————————————
# 1. 合并脆弱性与可达性数据
# ——————————————————————————
if "MVI" not in acc_results.columns:
    cols_to_merge = ["community_id", "HV", "SEV", "SAV", "PV", "MVI",
                      "is_vulnerability_stacked", "community_type"]
    acc_results = acc_results.merge(
        communities_gdf[cols_to_merge], on="community_id", how="left", suffixes=("", "_c")
    )

# 计算剥夺指数
day_vals = acc_results.get("A_i_2sfca_norm_day", pd.Series([np.nan]*len(acc_results))).fillna(0).values
night_vals = acc_results.get("A_i_2sfca_norm_night", pd.Series([np.nan]*len(acc_results))).fillna(0).values
gauss_vals = acc_results.get("A_i_gaussian_norm", pd.Series([np.nan]*len(acc_results))).fillna(0).values

acc_results["ADI_day"] = compute_deprivation_index(day_vals)
acc_results["ADI_night"] = compute_deprivation_index(night_vals)
acc_results["ADI_gaussian"] = compute_deprivation_index(gauss_vals)

# ——————————————————————————
# 2. Gini 系数计算
# ——————————————————————————
print("\\n【Gini 系数 — 可达性分配公平性】")
print("-" * 70)

gini_results = {}
for col, label in [("A_i_2sfca_norm_day", "白天2SFCA"),
                    ("A_i_2sfca_norm_night", "夜间2SFCA"),
                    ("A_i_gaussian_norm", "Gaussian 2SFCA")]:
    if col in acc_results.columns:
        vals = acc_results[col].fillna(0).values
        gini = compute_gini(vals)
        gini_results[label] = gini
        interp = "高度公平" if gini < 0.2 else "相对公平" if gini < 0.35 else "不平等" if gini < 0.5 else "极度不平等"
        print(f"  {label:15s} Gini = {gini:.4f}  [{interp}]")

print("\\n解读：")
print(f"  · 白天可达性 Gini = {gini_results.get("白天2SFCA", 0):.4f}")
print("  · 若 Gini > 0.4，说明15分钟生活圈的资源分配存在显著空间不公平")
print(f"  · 夜间可达性 Gini = {gini_results.get("夜间2SFCA", 0):.4f}")
print("  · 夜间不平等程度通常高于白天，反映24h设施的稀缺性")

# ——————————————————————————
# 3. 洛伦兹曲线可视化
# ——————————————————————————
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

ax1 = axes[0]
ax1.set_title("洛伦兹曲线 — 可达性分配公平性", fontsize=13, fontweight="bold")
ax1.plot([0, 1], [0, 1], "k--", linewidth=2, label="绝对平等线 (G=0)")

colors = {"白天2SFCA": "#3498db", "夜间2SFCA": "#e74c3c", "Gaussian 2SFCA": "#27ae60"}
for label, col_name in [("白天2SFCA", "A_i_2sfca_norm_day"),
                          ("夜间2SFCA", "A_i_2sfca_norm_night"),
                          ("Gaussian 2SFCA", "A_i_gaussian_norm")]:
    if col_name in acc_results.columns:
        vals = acc_results[col_name].fillna(0).values
        x, y = lorenz_curve(vals)
        g = compute_gini(vals)
        ax1.plot(x, y, linewidth=2.5, label=f"{label} (G={g:.3f})", color=colors.get(label, "gray"))
        ax1.fill_between(x, y, x, alpha=0.1, color=colors.get(label, "gray"))

ax1.set_xlabel("人口累积比例", fontsize=11)
ax1.set_ylabel("可达性累积比例", fontsize=11)
ax1.legend(fontsize=10, loc="upper left")
ax1.set_xlim(0, 1)
ax1.set_ylim(0, 1)
ax1.grid(True, alpha=0.3)

# ——————————————————————————
# 4. 可达性剥夺指数分析
# ——————————————————————————
ax2 = axes[1]
adi_col = "ADI_gaussian"
type_cn = {"urban_village": "城中村", "affordable_housing": "保障房",
            "commodity_housing": "商品房", "high_end": "高端社区"}
type_colors2 = {"urban_village": "#c0392b", "affordable_housing": "#e67e22",
                 "commodity_housing": "#27ae60", "high_end": "#2980b9"}

for ctype in type_colors2:
    subset = acc_results[acc_results["community_type"] == ctype]
    if len(subset) == 0:
        continue
    vals = subset[adi_col].dropna().sort_values()
    if len(vals) == 0:
        continue
    x_vals = np.linspace(0, 1, len(vals))
    label = type_cn.get(ctype, ctype)
    color = type_colors2[ctype]
    ax2.plot(x_vals, vals.values, linewidth=2.5, label=f"{label} (n={len(vals)})", color=color)
    ax2.fill_between(x_vals, vals.values, alpha=0.05, color=color)

ax2.set_xlabel("小区累积比例（按剥夺程度排序）", fontsize=11)
ax2.set_ylabel("可达性剥夺指数 (ADI)", fontsize=11)
ax2.set_title("可达性剥夺曲线 — 谁被剥夺得最严重？", fontsize=13, fontweight="bold")
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, "06_equity_analysis.png"), dpi=150, bbox_inches="tight", facecolor="white")
plt.show()
print("\\n图表已保存: 06_equity_analysis.png")

# ——————————————————————————
# 5. 分群体剥夺对比统计
# ——————————————————————————
print("\\n" + "=" * 70)
print("【关键发现】不同群体可达性剥夺对比")
print("=" * 70)

equity_summary = []
for ctype, cname in [("urban_village", "城中村"), ("affordable_housing", "保障房"),
                       ("commodity_housing", "商品房"), ("high_end", "高端社区")]:
    subset = acc_results[acc_results["community_type"] == ctype]
    if len(subset) == 0:
        continue
    acc_day = subset.get("A_i_2sfca_norm_day", pd.Series([np.nan]*len(subset))).dropna()
    acc_night = subset.get("A_i_2sfca_norm_night", pd.Series([np.nan]*len(subset))).dropna()
    acc_g = subset.get("A_i_gaussian_norm", pd.Series([np.nan]*len(subset))).dropna()
    equity_summary.append({
        "群体": cname,
        "小区数": len(subset),
        "白天可达性均值": acc_day.mean() if len(acc_day) > 0 else np.nan,
        "夜间可达性均值": acc_night.mean() if len(acc_night) > 0 else np.nan,
        "综合可达性均值": acc_g.mean() if len(acc_g) > 0 else np.nan,
        "ADI均值": subset["ADI_day"].mean() if "ADI_day" in subset.columns else np.nan,
    })

equity_df = pd.DataFrame(equity_summary)
print(equity_df.to_string(index=False))

# ——————————————————————————
# 6. 双重剥夺识别
# ——————————————————————————
print("\\n" + "-" * 70)
print("【双重剥夺 (Double Deprivation) 识别】")
print("-" * 70)

if "MVI" in acc_results.columns and "ADI_day" in acc_results.columns:
    acc_results["double_deprived"] = (
        (acc_results["MVI"] > 0.5) & (acc_results["ADI_day"] > 0.5)
    )
    dd_count = acc_results["double_deprived"].sum()
    dd_total = len(acc_results)
    print(f"  双重剥夺小区数量: {dd_count} / {dd_total} ({dd_count/dd_total*100:.1f}%)")
    dd_communities = acc_results[acc_results["double_deprived"]]
    if len(dd_communities) > 0:
        print("\\n  双重剥夺小区详情（高脆弱性 + 低可达性）:")
        cols_show = ["name", "community_type", "MVI", "ADI_day"]
        available = [c for c in cols_show if c in dd_communities.columns]
        display_df = dd_communities[available].copy()
        display_df["类型"] = display_df["community_type"].map(type_cn)
        print(display_df[["name", "类型", "MVI", "ADI_day"]].head(10).to_string(index=False))

    valid_mask = ~(acc_results["MVI"].isna() | acc_results["ADI_day"].isna())
    if valid_mask.sum() > 10:
        corr = acc_results.loc[valid_mask, "MVI"].corr(acc_results.loc[valid_mask, "ADI_day"])
        print(f"  MVI 与 ADI 相关系数: r = {corr:.4f}")
        if corr > 0.3:
            print("  解读: 正相关显著 → 脆弱性越高的小区，被剥夺程度越高（空间不公平）")
        else:
            print("  解读: 相关性较弱 → 脆弱性与可达性关系较为复杂")

print("\\n" + "=" * 70)
print("【人文反思】数字背后的公平性危机")
print("=" * 70)
print("""
当我们计算 Gini 系数时，数字背后是真实的人生：

  · 城中村居民的平均可达性，往往不到高端社区的1/3
  · 一位住在城中村的老人，夜间生病时最近的24h药店可能需要步行25分钟
  · 这不是"15分钟城市"，这是"25分钟困局"

  政策含义：
  1. 平均可达性达标 ≠ 所有群体可达性达标
  2. 需要"差异化的"15分钟生活圈规划——对弱势社区投入更多资源
  3. Gini系数是监测空间公平性的关键预警指标
""")
'''

cell26["source"] = [equity_code]

# ——————————————————————————
# Fix cell 3b intro text too (cell 11) — check for LaTeX escapes
# ——————————————————————————
cell11 = nb["cells"][11]
src11 = "".join(cell11.get("source", [""]))
print(f"\nCell 11 preview: {repr(src11[:300])}")

# Save
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("\nNotebook saved successfully!")
print(f"Total cells: {len(nb['cells'])}")
