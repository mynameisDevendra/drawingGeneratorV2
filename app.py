import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5  # 1.5 cm safety distance
FIXED_GAP = 33        # Locked inter-terminal distance in points
PAGE_SIZE = landscape(A3)

def parse_fixed_format(text):
    """Parses TXT lines and standardizes to Capital Letters."""
    new_rows = []
    try:
        # Standardize: remove extra spaces and handle case
        parts = [p.strip() for p in text.split(',')]
        row_id_match = re.search(r'^([A-Z]|\d+)', parts[0], re.I)
        if not row_id_match: return None
        rid = row_id_match.group(1).upper()
        
        for group in parts[1:]:
            # Regex handles spaces inside brackets automatically
            match = re.search(r'([^\[]+)\[\s*(\d+)\s+to\s+(\d+)\s*\]', group, re.I)
            if match:
                func_text = match.group(1).strip().upper() # Force Capital
                start = int(match.group(2))
                end = int(match.group(3))
                
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
    """Draws halved left column and 6-box footer for A3."""
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
        lines = text.upper().split('\n') # Force Capitals in Footer
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 15 - (idx * 10), line)
    return info_x

def process_drawing(df, fs, footer, left_col):
    """Processes multiple rows on A3 with fixed 33pt gap."""
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    
    df = df.dropna(subset=['Terminal Number']).drop_duplicates(subset=['Row ID', 'Terminal Number'])
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x_width = (width - (2 * PAGE_MARGIN)) / 12
    max_draw_w = width - (PAGE_MARGIN + info_x_width) - SAFETY_OFFSET - 40
    terminals_per_page = int(max_draw_w // FIXED_GAP)
    
    sheet_count = 1
    rows = df.groupby('Row ID')
    for rid, group in rows:
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_page] for i in range(0, len(terms), terminals_per_page)]
        for chunk in chunks:
            info_x = draw_page_template(c, width, height, footer, left_col, sheet_count)
            y_curr, x_start = height - 160, info_x + SAFETY_OFFSET + 20
            
            c.setFont("Helvetica-Bold", fs['row'])
            c.drawRightString(x_start - 30, y_curr + 15, str(rid).upper())
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * FIXED_GAP)
                c.setLineWidth(1); c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                c.circle(tx, y_curr+40, 3, stroke=1, fill=1); c.circle(tx, y_curr, 3, stroke=1, fill=1)
                c.setFont("Helvetica-Bold", fs['term']); c.drawRightString(tx-8, y_curr+17, str(t['Terminal Number']).zfill(2))
            
            for key, is_h, y_off in [('Function', True, 53.5), ('Cable Detail', False, -13.5)]:
                i = 0
                while i < len(chunk):
                    txt, s_x, j = str(chunk[i][key]).upper(), x_start + (i * FIXED_GAP), i
                    while j < len(chunk) and str(chunk[j][key]).upper() == txt:
                        e_x, j = x_start + (j * FIXED_GAP), j + 1
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
st.title("🚉 CTR Particular Generator (A3 Fixed 33pt)")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"Row ID": "A", "Function": "DID HHG (3RD)", "Cable Detail": "101-30C TO LOC-89", "Terminal Number": "01"},
        {"Row ID": "A", "Function": "DID HHG (3RD)", "Cable Detail": "101-30C TO LOC-89", "Terminal Number": "02"}
    ])

with st.sidebar:
    st.header("Settings")
    st.caption("Page Size: A3 (Locked) | Spacing: 33pt (Locked)")
    with st.expander("📏 Manual Font Sizes", expanded=False):
        fs = {'head': st.number_input("Function Font", 8.0), 'foot': st.number_input("Cable Detail Font", 7.0), 'term': st.number_input("Terminal Number Font", 7.0), 'row': st.number_input("Row ID Font", 12.0)}
    with st.expander("📝 Info Box & Footer", expanded=False):
        l_col = {'line1': st.text_input("Line 1", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
        f_data = {f"box{i+1}": st.text_area(f"Footer {i+1}", f"Label {i+1}", height=60) for i in range(6)}

st.subheader("Data Upload")
st.markdown("""**Format Guide**: `Row ID, Function [Start to End]`  
*Example: A, DID HHG [1 to 10]*""")

uploaded_file = st.file_uploader("Upload .txt file", type=["txt"])
if uploaded_file:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    all_parsed = []
    for line in stringio:
        if line.strip():
            parsed = parse_fixed_format(line.strip())
            if parsed: all_parsed.extend(parsed)
    if all_parsed: 
        st.session_state.df = pd.DataFrame(all_parsed)
        st.success("File processed! All text converted to Standard Capitals.")

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🗑️ Reset Table"):
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Function", "Cable Detail", "Terminal Number"]); st.rerun()

if st.button("🚀 Generate A3 PDF"):
    if not st.session_state.df.empty:
        pdf = process_drawing(st.session_state.df, fs, f_data, l_col)
        st.download_button("⬇️ Download Drawing", data=pdf, file_name="CTR_Particular_A3.pdf")