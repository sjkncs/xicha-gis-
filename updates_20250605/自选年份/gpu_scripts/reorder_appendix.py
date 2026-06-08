import re

tex_path = 'e:/xicha gis 智能定位/papers/conference-slides/会议论文/15min可达性幻觉/overleaf_paper/main_sci.tex'

with open(tex_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the street view appendix section (lines 865-886 approx)
# Pattern: from \section{Appendix: Street View...} to before \end{document}
sv_pattern = r'(\n\\section\{Appendix: Street View Image Analysis Results\}.*?)(?=\n\\end\{document\})'
sv_match = re.search(sv_pattern, content, re.DOTALL)

if not sv_match:
    print("Street View appendix not found!")
else:
    sv_section = sv_match.group(1)
    print(f"Found Street View appendix ({len(sv_section)} chars)")
    
    # Remove it from original location
    content_without_sv = content[:sv_match.start()] + content[sv_match.end():]
    
    # Find the Urban Renewal appendix (the one before DL Model Architecture)
    # Insert Street View between Urban Renewal and DL Model
    # We need to insert after the table that ends DL Model section
    
    # Find the DL Model Architecture section header
    dl_model_match = re.search(r'(\n\\section\{Appendix: Deep Learning Model Architecture\})', content_without_sv)
    if dl_model_match:
        insert_pos = dl_model_match.start()
        content_final = content_without_sv[:insert_pos] + sv_section + content_without_sv[insert_pos:]
        
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(content_final)
        print("SUCCESS: Street View appendix moved before DL Model Architecture")
        print(f"New file length: {len(content_final)} chars")
    else:
        print("DL Model Architecture section not found!")
