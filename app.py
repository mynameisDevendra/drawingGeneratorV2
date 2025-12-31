import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io
import zipfile
from datetime import datetime

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20
SAFETY_OFFSET = 42.5
FIXED_GAP = 33
PAGE_SIZE = landscape(A3)
ROW_HEIGHT_SPACING = 105 

def parse_fixed_format_multi_function(text):
    new_rows = []
    try:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) < 2: return None
        rid = parts[0].upper()
        term_keywords = ["SPARE", "RESERVED", "NI", "E3", "TERMINAL", "BLOCK", "LINK", "RESERVE"]
        last_part = parts[-1].upper()
        is_cable = not any(key in last_part for key in term_keywords)
        
        if is_cable and len(parts) >= 3:
            cable_detail = last_part
            middle_part = ",".join(parts[1:-1])
        else:
            cable_detail = "" 
            middle_part = ",".join(parts[1:])
            
        pattern = r'([^,\[]+)\[\s*(\d+)\s+to\s+(\d+)\s*\]'
        matches = re.findall(pattern, middle_part, re.I)
        
        for match in matches:
            func_text = match[0].strip().upper()
            start, end = int(match[1]), int(match[2])
            for i in range(start, end + 1):
                new_rows.append({
                    "Row ID": rid, "Function": func_text, 
                    "Cable Detail": cable_detail, "Terminal Number": str(i).zfill(2)
                })
        return new_rows
    except Exception:
        return None

def draw_page_template(c, width, height, footer_values, current_page, page_heading):
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, page_heading.upper())
    
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    total_footer_w = width - (2 * PAGE_MARGIN)
    info_x_width = total_footer_w / 15  
    info_x = PAGE_MARGIN + info_x_width
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    
    remaining_w = total_footer_w - info_x_width
    box_w = remaining_w / 8
    dividers = [info_x + (i * box_w) for i in range(9)] 
    for x in dividers[:-1]: c.line(x, PAGE_MARGIN, x, footer_y)

    # REPLACED SHEET NO with SHEET NAME
    headers = ["PREPARED BY", "CHECKED BY", "CHECKED BY", "APPROVED BY", "SHEET NAME", "RR/GOOMTY NO.", "STATION", "SIP", "PAGE NO."]
    for i in range(9):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        c.setFont("Helvetica-Bold", 4.5); c.drawCentredString(x_c, footer_y - 12, headers[i])
        c.setFont("Helvetica", 6.5)
        
        # Logic for Page No vs Footer values
        val = f"{current_page:02}" if i == 8 else str(footer_values[i])
        
        lines = val.upper().split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 25 - (idx * 10), line)
    return info_x

def process_drawing(df, fs, footer_values, page_heading):
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x = PAGE_MARGIN + ((width - (2 * PAGE_MARGIN)) / 15)
    max_draw_w = width - info_x - SAFETY_OFFSET - 40
    terminals_per_row = int(max_draw_w // FIXED_GAP)
    
    current_page = 1
    y_start, y_curr = height - 160, height - 160
    rows_on_page = 0
    
    draw_page_template(c, width, height, footer_values, current_page, page_heading)
    
    for rid, group in df.groupby('Row ID', sort=False):
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        for chunk in chunks:
            if rows_on_page >= 6:
                c.showPage()
                current_page += 1
                draw_page_template(c, width, height, footer_values, current_page, page_heading)
                y_curr, rows_on_page = y_start, 0
            
            x_start = info_x + SAFETY_OFFSET + 20
            c.setFont("Helvetica-Bold", fs['row']); c.drawRightString(x_start - 30, y_curr + 15, str(rid))
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * FIXED_GAP)
                c.setLineWidth(1); c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                c.circle(tx, y_curr+40, 3, fill=1); c.circle(tx, y_curr, 3, fill=1)
                c.setFont("Helvetica-Bold", fs['term']); c.drawRightString(tx-8, y_curr+17, str(t['Terminal Number']).zfill(2))
            
            for key, is_h, y_off in [('Function', True, 53.5), ('Cable Detail', False, -13.5)]:
                i = 0
                while i < len(chunk):
                    txt = str(chunk[i][key]).upper().strip()
                    if not txt: i += 1; continue
                    start_i = i
                    while i < len(chunk) and str(chunk[i][key]).upper().strip() == txt: i += 1
                    end_i = i - 1
                    s_x, e_x = x_start + (start_i * FIXED_GAP), x_start + (end_i * FIXED_GAP)
                    c.setLineWidth(0.8); c.line(s_x-5, y_curr+y_off, e_x+5, y_curr+y_off); mid_x = (s_x+e_x)/2
                    c.setFont("Helvetica-Bold", fs['head' if is_h else 'foot'])
                    if is_h:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off-5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off-5)
                        c.drawCentredString(mid_x, y_curr+y_off+10, txt)
                    else:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off+5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off+5)
                        c.drawCentredString(mid_x, y_curr+y_off-15, txt)
            
            y_curr -= ROW_HEIGHT_SPACING
            rows_on_page += 1
            
    c.save(); buffer.seek(0); return buffer, current_page

# --- STREAMLIT UI ---
st.set_page_config(page_title="Batch CTR Generator", layout="wide")
st.title("🚉 Batch Generator: Sheet Name Mode")

with st.sidebar:
    st.header("⚙️ Global Settings")
    page_heading = st.text_input("Page Heading", "TERMINAL CHART / CTR PARTICULARS")
    
    with st.expander("📂 Batch Footer Details", expanded=True):
        prep_by = st.text_input("Prepared By", "NOVALINE")
        chk_by1 = st.text_input("Checked By 1", "SSE/SIG")
        chk_by2 = st.text_input("Checked By 2", "ASTE/SIG")
        app_by = st.text_input("Approved By", "DY.CSTE")
        sip_no = st.text_input("SIP No", "SIP/2025")
    
    st.info("💡 **Filename Extraction:**\n`STATION_SHEET-NAME_GOOMTY.txt`")
    fs = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}

uploaded_files = st.file_uploader("Upload .txt files", type=["txt"], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Generate ZIP Archive"):
        zip_buffer = io.BytesIO()
        current_date = datetime.now().strftime("%d-%m-%Y")
        
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for uploaded_file in uploaded_files:
                # 1. Filename Parsing (Station_SheetName_Goomty)
                fname = uploaded_file.name.replace(".txt", "")
                parts = fname.split("_")
                stn = parts[0] if len(parts) > 0 else "STATION"
                sheet_name = parts[1] if len(parts) > 1 else "LB-XX"
                goomty = parts[2] if len(parts) > 2 else "G-XX"
                
                # 2. Footer Assembly (Index 4 is now Sheet Name)
                f_vals = [prep_by, chk_by1, chk_by2, app_by, sheet_name, goomty, stn, sip_no, "AUTO"]

                # 3. Data Processing
                raw_text = uploaded_file.getvalue().decode("utf-8")
                all_parsed = []
                for line in raw_text.splitlines():
                    if line.strip():
                        parsed = parse_fixed_format_multi_function(line.strip())
                        if parsed: all_parsed.extend(parsed)
                
                if all_parsed:
                    df = pd.DataFrame(all_parsed)
                    pdf_content, total_pages = process_drawing(df, fs, f_vals, page_heading)
                    
                    # 4. ZIP Naming
                    dynamic_name = f"{goomty}_{sheet_name}_{stn}_PAGES-{total_pages:02}_{current_date}.pdf"
                    zip_file.writestr(dynamic_name, pdf_content.getvalue())

        zip_buffer.seek(0)
        st.download_button("📥 Download Batch ZIP", data=zip_buffer, file_name=f"CTR_Batch_{current_date}.zip")