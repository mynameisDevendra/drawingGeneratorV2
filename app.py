import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5 # 1.5 cm safety distance 

# --- BULK ENTRY PARSER ---
def parse_fixed_format(text):
    """Parses: A row, Label [1 to 5], Label [6 to 10] into individual rows."""
    new_rows = []
    try:
        parts = [p.strip() for p in text.split(',')]
        row_id_match = re.search(r'^([A-Z])', parts[0], re.I)
        if not row_id_match: return None
        rid = row_id_match.group(1).upper()
        
        for group in parts[1:]:
            match = re.search(r'([^\[]+)\[(\d+)\s+to\s+(\d+)\]', group, re.I)
            if match:
                h_text, start, end = match.group(1).strip(), int(match.group(2)), int(match.group(3))
                for i in range(start, end + 1):
                    new_rows.append({
                        "Row ID": rid, 
                        "Header": h_text, 
                        "Footer": "", 
                        "Terminal ID": str(i).zfill(2) # [cite: 4-12]
                    })
        return new_rows
    except: return None

# --- PAGE LAYOUT TEMPLATE ---
def draw_page_template(c, width, height, footer_data, left_col_data):
    c.setLineWidth(1.5)
    # Peripheral Boundary 
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    
    # Left column width matched to 1st footer box
    box_w = (width - (2 * PAGE_MARGIN)) / 6
    info_x = PAGE_MARGIN + box_w
    
    # Full-length vertical margin line 
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - 80, info_x, height - PAGE_MARGIN - 80)
    
    # 6-Box Footer Vertical Dividers
    for i in range(1, 6):
        c.line(PAGE_MARGIN + (i * box_w), PAGE_MARGIN, PAGE_MARGIN + (i * box_w), footer_y)
        
    # Text Placement
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())
    
    for i, box in enumerate(["box1", "box2", "box3", "box4", "box5", "box6"]):
        x_c = PAGE_MARGIN + (i * box_w) + (box_w / 2)
        lines = footer_data[box].split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 15 - (idx * 10), line.upper()) # 
    return info_x

# --- MAIN DRAWING ENGINE ---
def process_drawing(df, fs, footer, left_col, page_size, gap):
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=size)
    width, height = size
    info_x = draw_page_template(c, width, height, footer, left_col)
    
    # Numerical sorting [cite: 4-12]
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows = df.groupby('Row ID')
    y_current, x_start = height - 160, info_x + SAFETY_OFFSET + 25
    
    for rid, group in rows:
        terms = group.to_dict('records')
        c.setFont("Helvetica-Bold", fs['row'])
        c.drawRightString(x_start - 35, y_current + 15, str(rid))
        
        for idx, t in enumerate(terms):
            tx = x_start + (idx * gap)
            # Terminal Symbol 
            c.setLineWidth(1); c.line(tx-3, y_current, tx-3, y_current+40); c.line(tx+3, y_current, tx+3, y_current+40)
            c.circle(tx, y_current+40, 3, stroke=1, fill=1); c.circle(tx, y_current, 3, stroke=1, fill=1)
            c.setFont("Helvetica-Bold", fs['term']); c.drawRightString(tx-8, y_current+17, str(t['Terminal ID']).zfill(2))
        
        # Grouping identical text [cite: 1, 2-8, 4-12]
        for key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terms):
                txt, s_x, j = str(terms[i][key]), x_start + (i * gap), i
                while j < len(terms) and str(terms[j][key]) == txt:
                    e_x, j = x_start + (j * gap), j + 1
                c.setLineWidth(0.8); c.line(s_x-5, y_current+y_off, e_x+5, y_current+y_off)
                mid = (s_x+e_x)/2
                c.setFont("Helvetica-Bold", fs['head' if is_h else 'foot'])
                if is_h:
                    c.line(s_x-5, y_current+y_off, s_x-5, y_current+y_off-5)
                    c.line(e_x+5, y_current+y_off, e_x+5, y_current+y_off-5)
                    c.line(mid, y_current+y_off, mid, y_current+y_off+5); c.drawCentredString(mid, y_current+y_off+10, txt)
                else:
                    c.line(s_x-5, y_current+y_off, s_x-5, y_current+y_off+5)
                    c.line(e_x+5, y_current+y_off, e_x+5, y_current+y_off+5)
                    c.line(mid, y_current+y_off, mid, y_current+y_off-5); c.drawCentredString(mid, y_current+y_off-15, txt)
                i = j
        y_current -= 160
    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Particular Generator", layout="wide")
st.title("🚉 CTR Particular Generator")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Header", "Footer", "Terminal ID"])

# Sidebar Customization
with st.sidebar:
    with st.expander("🛠️ Layout & Page", expanded=True):
        p_size = st.selectbox("Page Size", ["A4", "A3"])
        m_gap = st.slider("Terminal Spacing", 20, 60, 35)
    with st.expander("📏 Manual Font Sizes", expanded=False):
        fs = {'head': st.number_input("Header", 8.0), 'foot': st.number_input("Footer", 7.0), 'term': st.number_input("Terminal", 7.0), 'row': st.number_input("Row", 12.0)}
    with st.expander("📝 Page/Left Column Info", expanded=False):
        l_col = {'line1': st.text_input("Top Line", "COMPLETION DRAWING"), 'line2': st.text_input("Mid Line", "PCSTE'S REF NO."), 'line3': st.text_input("Bottom Line", "7132/24")}
    with st.expander("📂 Footer (6 Boxes)", expanded=False):
        f_data = {f"box{i+1}": st.text_area(f"Box {i+1}", f"Label {i+1}", height=60) for i in range(6)}

# Main Interface
st.subheader("Data Entry Methods")
tab1, tab2 = st.tabs(["🚀 Bulk Pattern Entry", "📊 Individual Terminal Entry"])

with tab1:
    st.info("Example: A row, DD DG [1 to 4], DD HHG [5 to 8], SPARES [9 to 30]")
    nlp_input = st.text_input("Enter pattern:")
    if st.button("Add Pattern"):
        parsed = parse_fixed_format(nlp_input)
        if parsed:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(parsed)], ignore_index=True)
            st.success("Pattern added to table below!")

with tab2:
    st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
    if st.button("🗑️ Clear All Data"):
        st.session_state.df = pd.DataFrame(columns=["Row ID", "Header", "Footer", "Terminal ID"])
        st.rerun()

# Generation
if st.button("🚀 Generate PDF Drawing"):
    if not st.session_state.df.empty:
        pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, m_gap)
        st.download_button("⬇️ Download PDF Drawing", data=pdf, file_name="CTR_Particular_Drawing.pdf", mime="application/pdf")
    else:
        st.warning("Please add terminal data first.")