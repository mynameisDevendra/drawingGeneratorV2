import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io
from datetime import datetime

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20
SAFETY_OFFSET = 42.5
FIXED_GAP = 33
PAGE_SIZE = landscape(A3)
ROW_HEIGHT_SPACING = 105 

def parse_fixed_format_multi_function(text):
    """Refined Parser: Distinguishes between Terminal Details and Cable Details."""
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

def draw_page_template(c, width, height, footer_values, sheet_num, page_heading):
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

    headers = ["PREPARED BY", "CHECKED BY", "CHECKED BY", "APPROVED BY", "LB/CTR/RR NO.", "RR/GOOMTY NO.", "STATION", "SIP", "SHEET NO."]
    for i in range(9):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        c.setFont("Helvetica-Bold", 4.5); c.drawCentredString(x_c, footer_y - 12, headers[i])
        c.setFont("Helvetica", 6.5)
        val = f"{sheet_num:03}" if i == 8 else str(footer_values[i])
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
    
    sheet_count = 1
    y_start, y_curr = height - 160, height - 160
    rows_on_page = 0
    
    draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
    
    for rid, group in df.groupby('Row ID', sort=False):
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        for chunk in chunks:
            if rows_on_page >= 6:
                c.showPage()
                sheet_count += 1
                draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
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
    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Generator", layout="wide")
st.title("🚉 CTR Particular Generator")

with st.sidebar:
    # --- REDESIGNED PROFESSIONAL INSTRUCTIONS ---
    with st.expander("📘 USER MANUAL & INTERFACE GUIDE", expanded=False):
        st.markdown("### 1. Data Import Protocol")
        st.info("Input `.txt` files must follow the structural format below:")
        st.code("RowID, Function [Start to End], CableDetail")
        st.markdown("""
        - **Cable Detection:** If the last part contains 'SPARE' or 'NI', it is treated as a Function. Otherwise, it is tagged as a Cable Detail.
        - **Multi-Function:** Separate multiple functions in one row using commas.
        """)
        
        st.markdown("### 2. Interface Features")
        st.markdown("""
        - **Dynamic Editor:** Edit cell values directly in the table before printing.
        - **Data Download:** Hover over the table top-right to find the **'Download as CSV'** icon to save your edited table.
        - **Row Management:** Scroll to the bottom of the table to add or delete rows manually.
        """)

        st.markdown("### 3. Execution Workflow")
        st.write("1. Upload TXT file.")
        st.write("2. Validate entries in the Editor.")
        st.write("3. Configure 'Page Setting'.")
        st.write("4. Execute 'Generate PDF'.")

    st.divider()
    st.header("⚙️ Page Setting")
    page_heading = st.text_input("Page Heading", "TERMINAL CHART / CTR PARTICULARS")
    with st.expander("📂 Footer Details"):
        f_vals = [st.text_input("Prepared By", "NOVALINE"), st.text_input("Checked By 1", "SSE/SIG"), 
                  st.text_input("Checked By 2", "ASTE/SIG"), st.text_input("Approved By", "DY.CSTE"), 
                  st.text_input("LB/CTR/RR No", "CTR-01"), st.text_input("Goomty No", "G-05"), 
                  st.text_input("Station", "STATION NAME"), st.text_input("SIP No", "SIP/2025"), "AUTO"]
    fs = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}

uploaded_file = st.file_uploader("Upload .txt file for Terminal Content", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    all_parsed = []
    for line in raw_text.splitlines():
        if line.strip():
            parsed = parse_fixed_format_multi_function(line.strip())
            if parsed: all_parsed.extend(parsed)
    if all_parsed:
        st.session_state.df = pd.DataFrame(all_parsed).reset_index(drop=True)
        st.success(f"Successfully loaded {len(st.session_state.df)} terminals.")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Function": "SPARE", "Cable Detail": "", "Terminal Number": "01"}])

# Table Interface Note
st.caption("💡 Tip: Use the icons at the top-right of the table below to download the data as a CSV or search for specific terms.")
st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing"):
    if not st.session_state.df.empty:
        pdf = process_drawing(st.session_state.df, fs, f_vals, page_heading)
        st.download_button("⬇️ Download PDF Drawing", data=pdf, file_name="CTR_Particulars.pdf")