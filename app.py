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
ROW_HEIGHT_SPACING = 120 

def parse_fixed_format_multi_function(text):
    """Protocol-based parser: Maps specific cable details to specific terminal ranges."""
    new_rows = []
    try:
        first_comma = text.find(',')
        if first_comma == -1: return None
        rid = text[:first_comma].strip().upper()
        
        last_comma = text.rfind(',')
        if last_comma <= first_comma:
            cable_detail = ""
            middle_part = text[first_comma+1:].strip()
        else:
            cable_detail = text[last_comma+1:].strip().upper()
            middle_part = text[first_comma+1:last_comma].strip()
        
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
    except Exception: return None

def draw_page_template(c, width, height, footer_values, left_col_data, sheet_num):
    """Draws 9-compartment title block with fixed headers."""
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    
    total_footer_w = width - (2 * PAGE_MARGIN)
    info_x_width = total_footer_w / 15  
    info_x = PAGE_MARGIN + info_x_width
    
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - 80, info_x, height - PAGE_MARGIN - 80)
    
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

def process_drawing(df, fs, footer_values, left_col):
    """Refactored logic for multi-cable vertical stacking."""
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    
    df = df.dropna(subset=['Terminal Number']).drop_duplicates(subset=['Row ID', 'Terminal Number'])
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x_width = (width - (2 * PAGE_MARGIN)) / 15
    info_x = PAGE_MARGIN + info_x_width
    max_draw_w = width - info_x - SAFETY_OFFSET - 40
    terminals_per_row = int(max_draw_w // FIXED_GAP)
    
    sheet_count = 1; y_curr = height - 160 
    draw_page_template(c, width, height, footer_values, left_col, sheet_count)
    
    rows = df.groupby('Row ID')
    for rid, group in rows:
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        
        for chunk in chunks:
            if y_curr < 200: 
                c.showPage(); sheet_count += 1
                draw_page_template(c, width, height, footer_values, left_col, sheet_count)
                y_curr = height - 160
            
            x_start = info_x + SAFETY_OFFSET + 20
            c.setFont("Helvetica-Bold", fs['row']); c.drawRightString(x_start - 30, y_curr + 15, str(rid).upper())
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * FIXED_GAP)
                c.setLineWidth(1); c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                c.circle(tx, y_curr+40, 3, stroke=1, fill=1); c.circle(tx, y_curr, 3, stroke=1, fill=1)
                c.setFont("Helvetica-Bold", fs['term']); c.drawRightString(tx-8, y_curr+17, str(t['Terminal Number']).zfill(2))
            
            for key, is_h, y_off in [('Function', True, 53.5), ('Cable Detail', False, -13.5)]:
                i = 0
                while i < len(chunk):
                    txt = str(chunk[i][key]).upper().strip()
                    if not txt: 
                        i += 1
                        continue
                    start_i = i
                    while i < len(chunk) and str(chunk[i][key]).upper().strip() == txt:
                        i += 1
                    end_i = i - 1
                    s_x, e_x = x_start + (start_i * FIXED_GAP), x_start + (end_i * FIXED_GAP)
                    c.setLineWidth(0.8); c.line(s_x-5, y_curr+y_off, e_x+5, y_curr+y_off); mid_x = (s_x+e_x)/2
                    c.setFont("Helvetica-Bold", fs['head' if is_h else 'foot'])
                    if is_h:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off-5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off-5)
                        c.line(mid_x, y_curr+y_off, mid_x, y_curr+y_off+5); c.drawCentredString(mid_x, y_curr+y_off+10, txt)
                    else:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off+5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off+5)
                        c.line(mid_x, y_curr+y_off, mid_x, y_curr+y_off-5); c.drawCentredString(mid_x, y_curr+y_off-15, txt)
            y_curr -= ROW_HEIGHT_SPACING 
    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Particular Generator", layout="wide")
st.title("🚉 CTR Particular Generator")

# --- SIDEBAR: PROTOCOL & SETTINGS ---
with st.sidebar:
    st.header("📖 TXT Format Protocol")
    st.markdown("""
    **To show separate cable brackets on the same row, follow this rule:**
    1. **One Line Per Cable**: Each line in your `.txt` file represents one cable.
    2. **Same Row ID**: Keep the Row ID same to stack horizontally.
    3. **Example**:
    ```text
    A, DID HHG [1 to 5], CABLE-01
    A, SPARES [6 to 10], CABLE-02
    ```
    """)
    st.divider()
    st.header("Project Details")
    with st.expander("📂 Footer Settings", expanded=False):
        f_vals = [
            st.text_input("Prepared by", "NOVALINE"), 
            st.text_input("Checked by (1)", "SSE/SIG"), 
            st.text_input("Checked by (2)", "ASTE/SIG"), 
            st.text_input("Approved by", "DY.CSTE"), 
            st.text_input("LB/CTR/RR No.", "CTR-01"), 
            st.text_input("RR/Goomty No.", "G-05"), 
            st.text_input("Station", "BAITARANI ROAD"), 
            st.text_input("SIP Number", "SIP/BTRD/2025"), 
            "AUTO"
        ]
    fs = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}
    l_col = {'line1': "COMPLETION DRAWING", 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}

# --- MAIN INTERFACE ---
st.subheader("Data Upload")
uploaded_file = st.file_uploader("Upload .txt file (Follow sidebar protocol)", type=["txt"])

if uploaded_file:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    all_parsed = []
    for line in stringio:
        if line.strip():
            parsed = parse_fixed_format_multi_function(line.strip())
            if parsed: all_parsed.extend(parsed)
    if all_parsed: st.session_state.df = pd.DataFrame(all_parsed)

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Function": "DID HHG", "Cable Detail": "CABLE 1", "Terminal Number": "01"}])

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing"):
    if not st.session_state.df.empty:
        pdf = process_drawing(st.session_state.df, fs, f_vals, l_col)
        date_str = datetime.now().strftime("%d-%m-%Y")
        file_name = f"{f_vals[4]}_{f_vals[5]}_{f_vals[6]}_{date_str}.pdf".replace(" ", "_")
        st.download_button("⬇️ Download PDF Drawing", data=pdf, file_name=file_name)