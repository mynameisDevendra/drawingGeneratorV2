import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5 # 1.5 cm safety distance

def parse_fixed_format(text):
    """Parses pattern: A row, Function [1 to 5] into individual rows."""
    new_rows = []
    try:
        parts = [p.strip() for p in text.split(',')]
        # Identify Row ID (Prioritize Alphabetical Row ID as requested)
        row_id_match = re.search(r'^([A-Z])', parts[0], re.I)
        if not row_id_match: return None
        rid = row_id_match.group(1).upper()
        
        for group in parts[1:]:
            match = re.search(r'([^\[]+)\[(\d+)\s+to\s+(\d+)\]', group, re.I)
            if match:
                func_text, start, end = match.group(1).strip(), int(match.group(2)), int(match.group(3))
                for i in range(start, end + 1):
                    new_rows.append({
                        "Row ID": rid, 
                        "Function": func_text, 
                        "Cable Detail": "", 
                        "Terminal Number": str(i).zfill(2)
                    })
        return new_rows
    except: return None

def draw_page_template(c, width, height, footer_data, left_col_data, sheet_num):
    """Draws the halved left column and 6-box footer."""
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    
    total_footer_width = width - (2 * PAGE_MARGIN)
    info_x_width = total_footer_width / 12  
    info_x = PAGE_MARGIN + info_x_width
    
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - 80, info_x, height - PAGE_MARGIN - 80)
    
    remaining_w = total_footer_width - info_x_width
    other_box_w = remaining_w / 5
    dividers = [info_x] + [info_x + (i * other_box_w) for i in range(1, 6)]
    for x in dividers:
        c.line(x, PAGE_MARGIN, x, footer_y)

    c.setFont("Helvetica-Bold", 6)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 5)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    for i in range(6):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        text = f"SH NO: {sheet_num:03}" if i == 5 else str(footer_data[f"box{i+1}"])
        lines = text.split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 15 - (idx * 10), line.upper())
    return info_x

def process_drawing(df, fs, footer, left_col, page_size, gap):
    """Processes terminal drawing with 1.5cm offset."""
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    width, height = size
    c = canvas.Canvas(buffer, pagesize=size)
    
    # 1. Deduplicate and Sort
    df = df.dropna(subset=['Terminal Number']).drop_duplicates(subset=['Row ID', 'Terminal Number'])
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x_width = (width - (2 * PAGE_MARGIN)) / 12
    max_draw_w = width - (PAGE_MARGIN + info_x_width) - SAFETY_OFFSET - 40
    terminals_per_page = int(max_draw_w // gap)
    
    sheet_count = 1
    rows = df.groupby('Row ID')
    for rid, group in rows:
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_page] for i in range(0, len(terms), terminals_per_page)]
        for chunk in chunks:
            info_x = draw_page_template(c, width, height, footer, left_col, sheet_count)
            y_curr, x_start = height - 160, info_x + SAFETY_OFFSET + 20
            c.setFont("Helvetica-Bold", fs['row'])
            c.drawRightString(x_start - 30, y_curr + 15, str(rid))
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * gap)
                # Terminal Symbol Rendering
                c.setLineWidth(1); c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                c.circle(tx, y_curr+40, 3, stroke=1, fill=1); c.circle(tx, y_curr, 3, stroke=1, fill=1)
                c.setFont("Helvetica-Bold", fs['term']); c.drawRightString(tx-8, y_curr+17, str(t['Terminal Number']).zfill(2))
            
            # Brackets
            for key, is_h, y_off in [('Function', True, 53.5), ('Cable Detail', False, -13.5)]:
                i = 0
                while i < len(chunk):
                    txt, s_x, j = str(chunk[i][key]), x_start + (i * gap), i
                    while j < len(chunk) and str(chunk[j][key]) == txt:
                        e_x, j = x_start + (j * gap), j + 1
                    c.setLineWidth(0.8); c.line(s_x-5, y_curr+y_off, e_x+5, y_curr+y_off)
                    mid = (s_x+e_x)/2
                    c.setFont("Helvetica-Bold", fs['head' if is_h else 'foot'])
                    if is_h:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off-5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off-5)
                        c.line(mid, y_curr+y_off, mid, y_curr+y_off+5); c.drawCentredString(mid, y_curr+y_off+10, txt)
                    else:
                        c.line(s_x-5, y_curr+y_off, s_x-5, y_curr+y_off+5); c.line(e_x+5, y_curr+y_off, e_x+5, y_curr+y_off+5)
                        c.line(mid, y_curr+y_off, mid, y_curr+y_off-5); c.drawCentredString(mid, y_curr+y_off-15, txt)
                    i = j
            c.showPage(); sheet_count += 1
    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Particular Generator", layout="wide")
st.title("🚉 CTR Particular Generator")

# Initialize Session State with alphabetical examples
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"Row ID": "A", "Function": "DID HHG (3RD)", "Cable Detail": "101-30C TO LOC-89", "Terminal Number": "01"},
        {"Row ID": "A", "Function": "DID HHG (3RD)", "Cable Detail": "101-30C TO LOC-89", "Terminal Number": "02"}
    ])

with st.sidebar:
    st.header("Settings")
    with st.expander("🛠️ Layout Settings", expanded=False):
        p_size = st.selectbox("Page Size", ["A4", "A3"])
        m_gap = st.slider("Terminal Spacing (Gap)", 20, 60, 35)
    with st.expander("📏 Manual Font Sizes", expanded=False):
        fs = {'head': st.number_input("Function Font", 8.0), 'foot': st.number_input("Cable Detail Font", 7.0), 'term': st.number_input("Terminal Number Font", 7.0), 'row': st.number_input("Row ID Font", 12.0)}
    with st.expander("📝 Info Box & Footer", expanded=False):
        l_col = {'line1': st.text_input("Line 1", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
        f_data = {f"box{i+1}": st.text_area(f"Footer {i+1}", f"Label {i+1}", height=60) for i in range(6)}

st.subheader("Data Entry")
nlp_input = st.text_input("Bulk Entry (Format: A row, Function [1 to 4])", placeholder="A row, DD DG [1 to 4], SPARES [5 to 10]")
if st.button("🚀 Apply Bulk Data"):
    parsed = parse_fixed_format(nlp_input)
    if parsed:
        st.session_state.df = pd.DataFrame(parsed)
        st.success("Table updated with alphabetical Row IDs!")

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🗑️ Reset Table"):
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Function", "Cable Detail", "Terminal Number"]); st.rerun()

if st.button("🚀 Generate PDF Drawing"):
    if not st.session_state.df.empty:
        pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, m_gap)
        st.download_button("⬇️ Download Drawing", data=pdf, file_name="CTR_Particular_Drawing.pdf")