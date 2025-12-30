import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5  # 1.5 cm safety distance
FIXED_GAP = 33        
PAGE_SIZE = landscape(A3)
ROW_HEIGHT_SPACING = 120 # Vertical distance between rows

def parse_fixed_format(text):
    """Parses TXT lines into individual terminal rows."""
    new_rows = []
    try:
        parts = [p.strip() for p in text.split(',')]
        row_id_match = re.search(r'^([A-Z]|\d+)', parts[0], re.I)
        if not row_id_match: return None
        rid = row_id_match.group(1).upper()
        
        for group in parts[1:]:
            match = re.search(r'([^\[]+)\[\s*(\d+)\s+to\s+(\d+)\s*\]', group, re.I)
            if match:
                func_text = match.group(1).strip().upper() 
                start, end = int(match.group(2)), int(match.group(3))
                for i in range(start, end + 1):
                    new_rows.append({"Row ID": rid, "Function": func_text, "Cable Detail": "", "Terminal Number": str(i).zfill(2)})
        return new_rows
    except: return None

def draw_page_template(c, width, height, footer_values, left_col_data, sheet_num):
    """Draws peripheral boundary and fixed 7-compartment title block."""
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    
    total_footer_w = width - (2 * PAGE_MARGIN)
    info_x_width = total_footer_w / 12  
    info_x = PAGE_MARGIN + info_x_width
    
    # Left Column Logic
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - 80, info_x, height - PAGE_MARGIN - 80)
    
    # Footer Partitioning: Adjusted for 7 specific segments
    # We maintain info_x as the first divider, then split remaining width
    remaining_w = total_footer_w - info_x_width
    box_w = remaining_w / 6
    dividers = [info_x + (i * box_w) for i in range(7)] 
    
    for x in dividers[:-1]: 
        c.line(x, PAGE_MARGIN, x, footer_y)

    # Permanent Left Info
    c.setFont("Helvetica-Bold", 6)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 5)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    # Fixed Headers and Dynamic Values
    headers = ["PREPARED BY", "CHECKED BY", "CHECKED BY", "APPROVED BY", "STATION", "SIP", "SHEET NUMBER"]
    
    for i in range(7):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        
        # Draw Header Label
        c.setFont("Helvetica-Bold", 5)
        c.drawCentredString(x_c, footer_y - 12, headers[i])
        
        # Draw Dynamic Value
        c.setFont("Helvetica", 7)
        val = f"{sheet_num:03}" if i == 6 else str(footer_values[i])
        lines = val.upper().split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 25 - (idx * 10), line)
            
    return info_x

def process_drawing(df, fs, footer_values, left_col):
    """Processes drawing on A3 with vertical stacking and fixed 33pt gap."""
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    
    df = df.dropna(subset=['Terminal Number']).drop_duplicates(subset=['Row ID', 'Terminal Number'])
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x = PAGE_MARGIN + ((width - (2 * PAGE_MARGIN)) / 12)
    max_draw_w = width - info_x - SAFETY_OFFSET - 40
    terminals_per_row = int(max_draw_w // FIXED_GAP)
    
    sheet_count = 1
    y_curr = height - 160 
    draw_page_template(c, width, height, footer_values, left_col, sheet_count)

    rows = df.groupby('Row ID')
    for rid, group in rows:
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        
        for chunk in chunks:
            if y_curr < 200: 
                c.showPage()
                sheet_count += 1
                draw_page_template(c, width, height, footer_values, left_col, sheet_count)
                y_curr = height - 160
            
            x_start = info_x + SAFETY_OFFSET + 20
            c.setFont("Helvetica-Bold", fs['row'])
            c.drawRightString(x_start - 30, y_curr + 15, str(rid).upper())
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * FIXED_GAP)
                # Terminal Symbol Rendering
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
            y_curr -= ROW_HEIGHT_SPACING 

    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Particular Generator", layout="wide")
st.title("🚉 CTR Particular Generator")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Function": "DID HHG", "Cable Detail": "101-30C", "Terminal Number": "01"}])

with st.sidebar:
    st.header("Customization")
    with st.expander("📏 Manual Font Sizes", expanded=False):
        fs = {'head': st.number_input("Function Font", 8.0), 'foot': st.number_input("Cable Detail Font", 7.0), 'term': st.number_input("Terminal Number Font", 7.0), 'row': st.number_input("Row ID Font", 12.0)}
    with st.expander("📝 Info Box (Permanent Left)", expanded=False):
        l_col = {'line1': st.text_input("Line 1", "COMPLETION DRAWING"), 'line2': st.text_input("Line 2", "PCSTE'S REF NO."), 'line3': st.text_input("Line 3", "7132/24")}
    with st.expander("📂 Footer Values", expanded=True):
        f_vals = [
            st.text_input("Prepared by", "NOVALINE"),
            st.text_input("Checked by (1)", "SSE/SIG"),
            st.text_input("Checked by (2)", "ASTE/SIG"),
            st.text_input("Approved by", "DY.CSTE"),
            st.text_input("Station", "BAITARANI ROAD"),
            st.text_input("SIP", "SIP/BTRD/2025"),
            "AUTO" # Sheet number handled automatically
        ]

st.subheader("Data Input")
uploaded_file = st.file_uploader("Upload .txt file (Format: A, Function [1 to 10])", type=["txt"])
if uploaded_file:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    all_parsed = []
    for line in stringio:
        if line.strip():
            parsed = parse_fixed_format(line.strip())
            if parsed: all_parsed.extend(parsed)
    if all_parsed: st.session_state.df = pd.DataFrame(all_parsed)

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate A3 PDF"):
    pdf = process_drawing(st.session_state.df, fs, f_vals, l_col)
    st.download_button("⬇️ Download Drawing", data=pdf, file_name="CTR_Particular_Final.pdf")