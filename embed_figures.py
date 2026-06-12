# -*- coding: utf-8 -*-
"""Embed figures into the final report"""
import sys, os, re
sys.path.insert(0, r'E:\xicha gis 智能定位')

from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = r'E:\xicha gis 智能定位'

# Map figure captions to actual file paths
# These are the key research figures from the project
FIGURE_MAP = {
    # Chapter 1 - Introduction
    '（图1：综合可达性分布图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig3_spatial.png'),
    '（图2：街景障碍物分布图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig7_saii_analysis.png'),
    '（图3：三类幻觉维度示意图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig1_framework.png'),

    # Chapter 2 - Data & Framework
    '（表1：多源数据汇总表）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig10_streetview_methodology.png'),
    '（图5：研究框架技术路线图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig1_framework.png'),
    '（图6：时间贫困指数空间聚类图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig6_time_poverty.png'),

    # Chapter 3 - Spatial Atlas
    '（图7：综合可达性与幻觉指数双变量地图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig3_spatial.png'),
    '（图8：四象限散点图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig4_illusion_scatter.png'),
    '（图9：街道障碍物空间分布图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig7_saii_analysis.png'),
    '（图10：弱势群体剥夺热点图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig6_deprived_communities.png'),
    '（图11：步行环境四维评分雷达图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig5_radar.png'),
    '（图12：供需匹配三维框架图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig9_supply_demand.png'),
    '（图13：时间贫困与幻觉指数相关性图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig6_time_poverty.png'),
    '（图14：昼夜达标率对比图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig8_day_night.png'),

    # Chapter 4 - Cross-district
    '（图15：四区障碍评分对比箱线图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig7_saii_analysis.png'),
    '（图16：四区障碍评分对比箱线图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'v2_real_data', 'p8_fig7_saii_analysis.png'),
    '（图17：四区对比机制路径图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig5_type_analysis.png'),
    '（图18：四区对比机制路径图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'conference_paper', 'figures', 'fig5_type_analysis.png'),

    # Chapter 5 - Governance
    '（图19：治理建议实施路径图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig1_framework.png'),
    '（图20：治理建议框架图）': os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures', 'fig1_framework.png'),
}

def add_image_to_paragraph(paragraph, image_path, width_inches=5.5):
    """Add an image to a paragraph by inserting after it"""
    if not os.path.exists(image_path):
        print(f"  [SKIP] Image not found: {image_path}")
        return False

    from docx.shared import Inches
    from lxml import etree

    # Add a new paragraph after the current one
    p = paragraph._element
    parent = p.getparent()
    idx = list(parent).index(p)

    # Create new paragraph for image
    new_p = OxmlElement('w:p')
    new_r = OxmlElement('w:r')
    new_drawing = OxmlElement('w:drawing')

    # Create inline image
    blip_fill = OxmlElement('a:blip', {
        'xmlns:r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'r:embed': 'rId999'
    })

    extent = OxmlElement('wp:extent', {
        'xmlns:wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing/inline/1',
        'cx': str(int(width_inches * 914400)),
        'cy': str(int(width_inches * 914400 * 0.6))
    })

    doc_pr = OxmlElement('wp:docPr', {
        'id': '999',
        'name': 'Figure',
        'descr': os.path.basename(image_path)
    })

    inline = OxmlElement('wp:inline', {
        'xmlns:wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing/inline/1',
        'distT': '0',
        'distB': '0',
        'distL': '0',
        'distR': '0'
    })
    inline.append(doc_pr)
    inline.append(extent)

    graphic = OxmlElement('a:graphic', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
    graphic_data = OxmlElement('a:graphicData', {
        'uri': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
    })
    pic = OxmlElement('pic:pic', {
        'xmlns:pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
    })

    nv_pic_pr = OxmlElement('pic:nvPicPr')
    c_nv_pic_pr = OxmlElement('pic:cNvPr', {
        'id': '999',
        'name': os.path.basename(image_path)
    })
    c_nv_pic_pic = OxmlElement('pic:cNvPic')
    pic_locks = OxmlElement('a:picLocks', {'noChangeAspect': '1'})
    c_nv_pic_pic.append(pic_locks)
    nv_pic_pr.append(c_nv_pic_pr)
    nv_pic_pr.append(c_nv_pic_pic)
    pic.append(nv_pic_pr)

    blip_fill2 = OxmlElement('a:blipFill', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
    blip_fill2.append(etree.Element('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}blip', {
        'embed': 'rId999'
    }))
    stretch = OxmlElement('a:stretch', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
    fill_rect = OxmlElement('a:fillRect', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'l': '0', 't': '0', 'r': '0', 'b': '0'})
    stretch.append(fill_rect)
    blip_fill2.append(stretch)
    pic.append(blip_fill2)

    sp_pr = OxmlElement('pic:spPr', {
        'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'xmlns:pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
        'bwMode': 'auto'
    })
    xfrm = OxmlElement('a:xfrm', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
    off = OxmlElement('a:off', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'x': '0', 'y': '0'})
    ext = OxmlElement('a:ext', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'cx': str(int(width_inches * 914400)), 'cy': str(int(width_inches * 914400 * 0.6))})
    xfrm.append(off)
    xfrm.append(ext)
    prstGeom = OxmlElement('a:prstGeom', {'xmlns:a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'prst': 'rect'})
    sp_pr.append(xfrm)
    sp_pr.append(prstGeom)
    pic.append(sp_pr)
    graphic_data.append(pic)
    graphic.append(graphic_data)
    inline.append(graphic)

    new_drawing.append(inline)
    new_r.append(new_drawing)
    new_p.append(new_r)

    parent.insert(idx + 1, new_p)

    # Add the image to the document's part
    doc = paragraph.part
    with open(image_path, 'rb') as f:
        img_bytes = f.read()

    # Add image to document
    rId = doc.part.relate_to(
        img_bytes,
        'image/png' if image_path.endswith('.png') else 'image/jpeg',
        part_name='/word/media/fig999.png'
    )

    # Update the rId in the blip
    blip_el = new_p.find('.//{http://schemas.openxmlformats.org/officeDocument/2006/relationships}blip')
    if blip_el is not None:
        blip_el.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed', rId)

    print(f"  [OK] Embedded: {os.path.basename(image_path)}")
    return True

def add_caption_paragraph(doc, after_para, caption_text):
    """Add a centered caption paragraph after a paragraph"""
    parent = after_para._element.getparent()
    idx = list(parent).index(after_para._element)

    cap_p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    jc = OxmlElement('w:jc', {'val': 'center'})
    pPr.append(jc)
    cap_p.append(pPr)

    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rFonts = OxmlElement('w:rFonts', {'w:eastAsia': '宋体', 'w:ascii': '宋体'})
    sz = OxmlElement('w:sz', {'val': '20'})
    rPr.append(rFonts)
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = caption_text
    r.append(t)
    cap_p.append(r)
    parent.insert(idx + 1, cap_p)

def embed_figures_in_doc(input_path, output_path):
    doc = Document(input_path)

    matched = 0
    skipped = 0

    for para in doc.paragraphs:
        text = para.text
        for caption, img_path in FIGURE_MAP.items():
            if caption in text:
                print(f"Found: {caption}")

                # Embed image after this paragraph
                if os.path.exists(img_path):
                    add_image_to_paragraph(para, img_path)
                    matched += 1
                else:
                    print(f"  [SKIP] Not found: {img_path}")
                    skipped += 1

                # Add caption
                cap_text = '图 ' + caption.replace('（', '').replace('）', '')
                add_caption_paragraph(doc, para, cap_text)
                break

    print(f"\nSummary: {matched} embedded, {skipped} skipped")
    doc.save(output_path)
    print(f"Saved to: {output_path}")

if __name__ == '__main__':
    input_doc = os.path.join(BASE, '报告_final.docx')
    output_doc = os.path.join(BASE, '报告_final_含图.docx')
    embed_figures_in_doc(input_doc, output_doc)
