import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5  # 1.5 cm distance from left column line

# --- NLP PARSER ENGINE ---
def parse_natural_language(text):
    """Parses conversational text into terminal data rows."""
    new_rows = []
    row_match = re.search(r'row\s+([A-Z])', text, re.I)
    header_match = re.search(r'header\s+([^,]+)', text, re.I)
    footer_match = re.search(r'footer\s+([^,]+)', text, re.I)
    range_match = re.search(r'terminals?\s+(\d+)\s+to\s+(\d+)', text, re.I)

    if row_match and range_match:
        rid = row_match.group(1).upper()
        h_text = header_match.group(1).strip() if header_match else "SPARE" [cite: 31, 41]
        f_text = footer_match.group(1).strip() if footer_match else ""
        start, end = int(range_match.group(1)), int(range_match.group(2))
        
        for i in range(start, end + 1):
            new_rows.append({
                "Row ID": rid,
                "Header": h_text,
                "Footer": f_text,
                "Terminal ID": str(i).zfill(2) [cite: 4-12]
            })
    return new_rows

# --- PAGE LAYOUT TEMPLATE ---
def draw_page_template(c, width, height, footer_data, left_col_data):
    c.setLineWidth(1.5)
    # Peripheral Boundary 
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    
    # 6-Box Footer Logic
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    box_width = (width - (2 * PAGE_MARGIN)) / 6
    
    # Full-Length Left Column aligned with 1st box divider
    info_column_x = PAGE_MARGIN + box_width 
    c.line(info_column_x, PAGE_MARGIN, info_column_x, height - PAGE_MARGIN)
    
    # Top Left Info Partition [cite: 1, 52]
    info_box_height = 80
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - info_box_height, info_column_x, height - PAGE_MARGIN - info_box_height)
    
    for i in range(1, 6):
        x_pos = PAGE_MARGIN + (i * box_width)
        c.line(x_pos, PAGE_MARGIN, x_pos, footer_y)
    
    # Render Left Column Text [cite: 1, 2, 52, 88]
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    # Render Footer Text [cite: 54-64, 85-88, 100]
    labels = ["box1", "box2", "box3", "box4", "box5", "box6"]
    for i, label in enumerate(labels):
        x_center = PAGE_MARGIN + (i * box_width) + (box_width / 2)
        lines = footer_data[label].split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_center, footer_y - 15 - (idx * 10), line.upper())

    return info_column_x

# --- DRAWING PRIMITIVES ---
def draw_terminal(c, x, y, term_id, term_font_size):
    """Draws terminal symbol as two vertical lines with solid circles [cite: 2-7, 9]."""
    c.setLineWidth(1)
    c.line(x - 3, y, x - 3, y + 40) 
    c.line(x + 3, y, x + 3, y + 40) 
    c.setFillColorRGB(0, 0, 0)
    c.circle(x, y + 40, 3, stroke=1, fill=1) 
    c.circle(x, y, 3, stroke=1, fill=1)      
    c.setFont("Helvetica-Bold", term_font_size)
    c.drawRightString(x - 8, y + 17, str(term_id).zfill(2)) 

def draw_bracket(c, x1, x2, y, text, is_header, user_font_size):
    """Draws grouping brackets with user-defined font size [cite: 2-8]."""
    c.setLineWidth(0.8)
    c.line(x1, y, x2, y)
    mid = (x1 + x2) / 2
    c.setFont("Helvetica-Bold", user_font_size)
    if is_header:
        c.line(x1, y, x1, y - 5); c.line(x2, y, x2, y - 5); c.line(mid, y, mid, y + 5)
        c.drawCentredString(mid, y + 10, str(text))
    else:
        c.line(x1, y, x1, y + 5); c.line(x2, y, x2, y + 5); c.line(mid, y, mid, y - 5)
        c.drawCentredString(mid, y - (user_font_size + 8), str(text))

# --- MAIN DRAWING ENGINE ---
def process_drawing(df, fs, footer, left_col, page_size, gap):
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=size)
    width, height = size
    
    info_x = draw_page_template(c, width, height, footer, left_col)
    
    # Sorting Logic [cite: 4-12]
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows = df.groupby('Row ID')
    y_current = height - 160
    x_start_base = info_x + SAFETY_OFFSET + 25

    for rid, group in rows:
        terms = group.to_dict('records')
        c.setFont("Helvetica-Bold", fs['row'])
        c.drawRightString(x_start_base - 35, y_current + 15, str(rid))

        for idx, t in enumerate(terms):
            draw_terminal(c, x_start_base + (idx * gap), y_current, t['Terminal ID'], fs['term'])

        # Grouping Headers and Footers [cite: 4-12, 14-23]
        for key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terms):
                txt = str(terms[i][key])
                s_x = x_start_base + (i * gap)
                j = i
                while j < len(terms) and str(terms[j][key]) == txt:
                    e_x = x_start_base + (j * gap)
                    j += 1
                draw_bracket(c, s_x - 5, e_x + 5, y_current + y_off, txt, is_h, fs['head' if is_h else 'foot'])
                i = j
        y_current -= 160

    c.save(); buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="Railway Terminal Designer", layout="wide")
st.title("🚉 Railway Terminal Manual Designer")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Header": "DID HHG (3RD)", "Footer": "101-30C TO LOC-89", "Terminal ID": "01"}])

with st.sidebar:
    st.header("Customization Settings")
    with st.expander("🛠️ Page & Manual Spacing", expanded=True):
        p_size = st.selectbox("Page Size", ["A4", "A3"])
        manual_gap = st.slider("Terminal Gap (Horizontal)", 20, 60, 35)
    
    with st.expander("📏 Manual Font Sizes", expanded=True):
        fs = {
            'head': st.number_input("Header Font", value=8.0),
            'foot': st.number_input("Footer Font", value=7.0),
            'term': st.number_input("Terminal ID Font", value=7.0),
            'row': st.number_input("Row ID Font", value=12.0)
        }
    
    with st.expander("📝 Left Column Info", expanded=False):
        l_col = {
            'line1': st.text_input("Top Line", "COMPLETION DRAWING"),
            'line2': st.text_input("Mid Line", "PCSTE'S REF NO."),
            'line3': st.text_input("Bottom Line", "7132/24")
        }
    
    with st.expander("📂 Footer (6 Boxes)", expanded=False):
        f_data = {
            'box1': st.text_area("Box 1", "PREPARED BY\nNOVALINE INFRA", height=60),
            'box2': st.text_area("Box 2", "CHECKED BY\nSSE/SIG", height=60),
            'box3': st.text_area("Box 3", "APPROVED BY\nDY.CSTE", height=60),
            'box4': st.text_area("Box 4", "LOCATION\nSOUTH GOOTY", height=60),
            'box5': st.text_area("Box 5", "STATION\nBAITARANI ROAD", height=60),
            'box6': st.text_area("Box 6", "SHEET INFO\nSH NO: 009", height=60)
        }

st.subheader("Data Entry")
tab1, tab2 = st.tabs(["🗨️ Natural Language Input", "📊 Manual Table Editor"])

with tab1:
    cmd = st.text_input("Enter Command:", placeholder="e.g. Row A, Header DID DG, Footer 101-30C, Terminals 01 to 05")
    if st.button("Apply Command"):
        parsed = parse_natural_language(cmd)
        if parsed:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(parsed)], ignore_index=True)
            st.success("Terminals added!")
        else:
            st.error("Invalid format.")

with tab2:
    st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing"):
    pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, manual_gap)
    st.download_button("⬇️ Download Drawing", data=pdf, file_name="Signaling_Drawing.pdf")