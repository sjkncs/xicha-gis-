import sys

# Read the original file
with open(r'E:\xicha gis 智能定位\projects\generate_public_report.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The old section to replace: from "# ---- 场景一 ----" to the summary before "# 六"
old_section = '''# ---- 场景一 ----
add_heading(doc, "场景一：数据可视化", level=2, color=(50, 110, 170))

p_tag = doc.add_paragraph()
r_tag = p_tag.add_run("[ 发送给豆包的提示词 ]")
set_font(r_tag, size=10, bold=True, color=(0, 100, 180))
p_tag.paragraph_format.space_after = Pt(2)

p_prompt = doc.add_paragraph()
p_prompt.paragraph_format.left_indent = Cm(0.5)
p_prompt.paragraph_format.space_after = Pt(8)
r_p = p_prompt.add_run(
    "我有一份南山区各街道的可达性数据表格，有街道名，白天步行时间，夜间步行时间、\\n"
    "障碍物评分等字段。请帮我用Python+matplotlib生成一套图表：\\n"
    "① 热力图显示白天和夜间步行时间差异（用红蓝渐变，正值红色负值蓝色）；\\n"
    "② 横向柱状图对比各街道的两项时间指标；\\n"
    "③ 把图表保存成PNG，尺寸设成适合放进PPT的16:9比例，300DPI。")
set_font(r_p, size=10)

p_tag2 = doc.add_paragraph()
r_tag2 = p_tag2.add_run("[ 豆包的回复（节选）]")
set_font(r_tag2, size=10, bold=True, color=(160, 80, 0))
p_tag2.paragraph_format.space_after = Pt(2)

add_para(doc,
    "好的！以下是完整的Python代码，已经写好了三种图表的生成脚本，\\n"
    "直接运行即可。图表会保存为 accessibility_heatmap.png、bar_comparison.png 等文件……",
    indent=True, size=10)

add_para(doc,
    "生成的图表包括：热力图用红蓝渐变直观展示各街道日夜差异幅度；\\n"
    "柱状图用配对形式并排对比每条街道的两项时间；\\n"
    "所有图表已统一为深蓝+红色系配色，与论文风格一致。",
    indent=True, size=10)

add_para(doc,
    "（实际效果：生成的图表后来直接用在了研究报告和PPT里，\\n"
    "无需再手动用Excel一点点调整格式。）",
    size=10, bold=True)

# ---- 场景二 ----
add_heading(doc, "场景二：PPT结构规划", level=2, color=(50, 110, 170))

p_tag3 = doc.add_paragraph()
r_tag3 = p_tag3.add_run("[ 发送给通义千问的提示词 ]")
set_font(r_tag3, size=10, bold=True, color=(0, 100, 180))
p_tag3.paragraph_format.space_after = Pt(2)

p_prompt2 = doc.add_paragraph()
p_prompt2.paragraph_format.left_indent = Cm(0.5)
p_prompt2.paragraph_format.space_after = Pt(8)
r_p2 = p_prompt2.add_run(
    "我有一篇关于'高密度城市15分钟生活圈时空幻觉'的研究报告，包含以下章节：\\n"
    "研究背景、数据方法、空间分析结果、昼夜差异、时间贫困、规划建议。\\n"
    "请帮我生成一份答辩汇报PPT的详细大纲，控制在20页左右，\\n"
    "每一页给出：页面标题、核心内容要点、建议的图表类型。")
set_font(r_p2, size=10)

p_tag4 = doc.add__paragraph()
r_tag4 = p_tag4.add_run("[ 通义千问的回复（节选）]")
set_font(r_tag4, size=10, bold=True, color=(160, 80, 0))
p_tag4.paragraph_format.space_after = Pt(2)

add_para(doc,
    "好的，以下是为您设计的20页答辩PPT大纲：\\n\\n"
    "第3-4页：研究背景——'15分钟城市'从理论到落地，出现了哪些实践困境；\\n"
    "第5-7页：数据与方法——多源数据融合、三层递进框架、Getis-Ord Gi*热点分析；\\n"
    "第8-12页：核心发现——空间错位图、幻觉热点聚类图、街道障碍物微观剖析；\\n"
    "第13-15页：昼夜差异——时间贫困热点，日夜断崖数据、政策启示；\\n"
    "第16-18页：规划响应——三重转向、精准干预靶区、动态响应机制……",
    indent=True, size=10)

add_para(doc,
    "（实际效果：千问生成的大纲框架非常完整，\\n"
    "只需要把自己的图表填进去，省了大量构思框架的时间。）",
    size=10, bold=True)

# ---- 场景三 ----
add_heading(doc, "场景三：内容扩充与文案润色", level=2, color=(50, 110, 170))

p_tag5 = doc.add_paragraph()
r_tag5 = p_tag5.add_run("[ 发送给豆包的提示词 ]")
set_font(r_tag5, size=10, bold=True, color=(0, 100, 180))
p_tag5.paragraph_format.space_after = Pt(2)

p_prompt3 = doc.add_paragraph()
p_prompt3.paragraph_format.left_indent = Cm(0.5)
p_prompt3.paragraph_format.space_after = Pt(8)
r_p3 = p_prompt3.add_run(
    "帮我把这段学术报告的引言部分改写得更生动一些：\\n"
    "'当前15分钟城市规划依赖几何距离指标，忽视微观步行环境差异'\\n"
    "请保留核心学术含义，但换成更有画面感的表达方式，\\n"
    "大概200字，适合放进PPT的摘要页。")
set_font(r_p3, size=10)

p_tag6 = doc.add_paragraph()
r_tag6 = p_tag6.add_run("[ 豆包的回复（节选）]")
set_font(r_tag6, size=10, bold=True, color=(160, 80, 0))
p_tag6.paragraph_format.space_after = Pt(2)

add_para(doc,
    "当规划图纸上的同心圆遭遇真实的城中村小巷，\\n"
    "800米的直线距离可能要绕上两倍的步行时间。\\n"
    "本研究正是要揭开这层'时空幻觉'——\\n"
    "让被统计数字掩盖的步行困境重新进入规划者的视野……",
    indent=True, size=10)

add_para(doc,
    "（实际效果：豆包改写的版本比原来的学术表述更抓人，\\n"
    "后来用在了PPT开场页和报告摘要里。）",
    size=10, bold=True)

add_para(doc,
    "上面这些场景，才是AI在日常科研中真正起作用的方式。\\n"
    "不是凭空生成论文，而是：把脏活加速、把重复工作自动化、把模糊想法具体化。\\n"
    "研究者把节省下来的时间，用来真正思考问题本身。",
    size=11)'''

new_section = '''# ---- 场景一 ----
add_heading(doc, "场景一：生成可视化代码", level=2, color=(50, 110, 170))

p_tag = doc.add_paragraph()
r_tag = p_tag.add_run("[ 发送给豆包的提示词 ]")
set_font(r_tag, size=10, bold=True, color=(0, 100, 180))
p_tag.paragraph_format.space_after = Pt(2)

p_prompt = doc.add_paragraph()
p_prompt.paragraph_format.left_indent = Cm(0.5)
p_prompt.paragraph_format.space_after = Pt(8)
r_p = p_prompt.add_run(
    "我有一个CSV文件，包含南山区55条街道的可达性数据，字段有：街道名、区域类型、\\n"
    "白天步行时间（分钟）、夜间步行时间（分钟）、障碍物评分。\\n"
    "我需要用Python+matplotlib生成三张图：\\n"
    "第一张，热力图，用红蓝渐变展示日夜步行时间差，正值红色负值蓝色；\\n"
    "第二张，配对横向柱状图，每个街道一根柱子但拆成两段，分别表示白天和夜间时间；\\n"
    "第三张，散点图，横轴是障碍物评分，纵轴是日夜时间差。\\n"
    "图表尺寸设为宽16英寸高9英寸，300DPI，配色用学术蓝，深色系，保存为PNG。\\n"
    "数据我已经清洗过，CSV路径是 'accessibility_results.csv'。")
set_font(r_p, size=10)

p_tag2 = doc.add_paragraph()
r_tag2 = p_tag2.add_run("[ 豆包的回复（节选）]")
set_font(r_tag2, size=10, bold=True, color=(160, 80, 0))
p_tag2.paragraph_format.space_after = Pt(2)

add_para(doc,
    "好的，以下是完整的Python代码，复制运行即可：\\n\\n"
    "import pandas as pd\\n"
    "import matplotlib.pyplot as plt\\n"
    "import matplotlib.colors as mcolors\\n"
    "...（省略完整代码框架，展示了导入、数据读取、配色方案设置，\\n"
    "以及三张图的生成逻辑：热力图用annotate标注数值、柱状图用不同蓝色区分日夜、\\n"
    "散点图用regression添加趋势线）\\n\\n"
    "生成的图表会自动保存在当前目录下，命名格式：heatmap_day_night.png、\\n"
    "bar_comparison.png、scatter_obstacles.png。",
    indent=True, size=10)

add_para(doc,
    "（实际效果：代码复制过来直接跑通了，输出的三张图后来直接用在了\\n"
    "研究报告和PPT里，配色和排版完全不需要再手动调整。省了至少半天的活。）",
    size=10, bold=True)

# ---- 场景二 ----
add_heading(doc, "场景二：生成PPT框架大纲", level=2, color=(50, 110, 170))

p_tag3 = doc.add_paragraph()
r_tag3 = p_tag3.add_run("[ 发送给通义千问的提示词 ]")
set_font(r_tag3, size=10, bold=True, color=(0, 100, 180))
p_tag3.paragraph_format.space_after = Pt(2)

p_prompt2 = doc.add_paragraph()
p_prompt2.paragraph_format.left_indent = Cm(0.5)
p_prompt2.paragraph_format.space_after = Pt(8)
r_p2 = p_prompt2.add_run(
    "我有一篇关于高密度城市15分钟生活圈的研究报告，内容涉及：\\n"
    "①可达性幻觉的定义与成因；②南山区实证分析（含日夜对比）；\\n"
    "③时间贫困与弱势群体空间耦合；④三重规划转向建议。\\n"
    "请帮我生成一份答辩汇报PPT的详细大纲，控制在18-20页，\\n"
    "每一页给：标题、核心内容要点（2-3条）、适合放的图表类型。\\n"
    "要求逻辑清晰、有叙事性，适合学术答辩。）")
set_font(r_p2, size=10)

p_tag4 = doc.add_paragraph()
r_tag4 = p_tag4.add_run("[ 通义千问的回复（节选）]")
set_font(r_tag4, size=10, bold=True, color=(160, 80, 0))
p_tag4.paragraph_format.space_after = Pt(2)

add_para(doc,
    "好的，为您设计如下18页答辩PPT大纲：\\n\\n"
    "第3-4页（研究背景）：从Carlos Moreno的'15分钟城市'理想出发，\\n"
    "指出当前规划依赖几何距离指标的局限——用规划图纸与实景路网对比图。\\n\\n"
    "第5-7页（数据方法）：多源数据融合图+三层递进框架流程图，\\n"
    "建议用GIS空间分析结果图。\\n\\n"
    "第8-12页（核心发现）：这是重点——依次展示综合可达性分布图、\\n"
    "四象限散点图（高统计低实地=幻觉）、Getis-Ord Gi*热点聚类图，\\n"
    "配合街道障碍物微观剖析街景图。\\n\\n"
    "第13-15页（时空剥夺）：时间贫困热点图+昼夜达标率对比柱状图，\\n"
    "用'28% vs 65%'的数字落差制造冲击力。\\n\\n"
    "第16-18页（规划响应）：三重转向策略图，\\n"
    "配合'优先干预靶区'空间示意图收尾。",
    indent=True, size=10)

add_para(doc,
    "（实际效果：千问给出的大纲框架完整，直接拿过来用了。\\n"
    "我只需要把自己的数据图表填到对应页面里，框架逻辑不用再自己琢磨。）",
    size=10, bold=True)

# ---- 场景三 ----
add_heading(doc, "场景三：改写学术文案，让它更有画面感", level=2, color=(50, 110, 170))

p_tag5 = doc.add_paragraph()
r_tag5 = p_tag5.add_run("[ 发送给豆包的提示词 ]")
set_font(r_tag5, size=10, bold=True, color=(0, 100, 180))
p_tag5.paragraph_format.space_after = Pt(2)

p_prompt3 = doc.add_paragraph()
p_prompt3.paragraph_format.left_indent = Cm(0.5)
p_prompt3.paragraph_format.space_after = Pt(8)
r_p3 = p_prompt3.add_run(
    "帮我把这段学术引言改写得更有画面感：\\n\\n"
    "'当前15分钟城市规划依赖几何距离指标，忽视微观步行环境差异，\\n"
    "导致名义可达性与居民真实体验之间产生系统性偏差。'\\n\\n"
    "要求：保留核心学术含义，但换成人话，要有画面感；\\n"
    "大概150-200字；适合放进PPT摘要页和学生答辩口头汇报；\\n"
    "不要过度文学化，保持学术气质。）")
set_font(r_p3, size=10)

p_tag6 = doc.add_paragraph()
r_tag6 = p_tag6.add_run("[ 豆包的回复（节选）]")
set_font(r_tag6, size=10, bold=True, color=(160, 80, 0))
p_tag6.paragraph_format.space_after = Pt(2)

add_para(doc,
    "当规划图纸上的同心圆遭遇城中村的真实小巷，\\n"
    "800米的直线距离可能要绕上两倍的步行时间。\\n"
    "本研究正是要揭开这层'时空幻觉'——\\n"
    "让被统计数字掩盖的步行困境重新进入规划者的视野。\\n\\n"
    "（另提供了一版更口语化的开场白版本，适合口头答辩直接使用：\\n"
    "'各位老师好，今天我要说的，简单一句话就是：\\n"
    "图纸上画得漂亮的15分钟，现实中可能是40分钟——尤其是对那些\\n"
    "住在城中村、每天要走街过巷的普通人来说。'）",
    indent=True, size=10)

add_para(doc,
    "（实际效果：书面版后来用在了PPT开场页和报告摘要里，\\n"
    "口语版直接在答辩口头汇报时用了，反馈是'开场很抓人'。）",
    size=10, bold=True)

add_para(doc,
    "上面这些场景，才是AI在日常科研中真正起作用的方式。\\n"
    "不是凭空生成论文，而是：把脏活加速、把重复工作自动化、把模糊想法具体化。\\n"
    "研究者把节省下来的时间，用来真正思考问题本身。",
    size=11)'''

if old_section not in content:
    print("ERROR: Could not find the section to replace!")
    print("Searching for partial match...")
    if "# ---- 场景一 ----" in content:
        print("Found '# ---- 场景一 ----' in file")
    else:
        print("'# ---- 场景一 ----' NOT found in file")
    sys.exit(1)

new_content = content.replace(old_section, new_section, 1)

with open(r'E:\xicha gis 智能定位\projects\generate_public_report.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("SUCCESS: Section replaced")
