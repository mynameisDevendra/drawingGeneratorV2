import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
import re
import io

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20  
SAFETY_OFFSET = 42.5 # 1.5 cm distance from left column [cite: 1, 53]

def draw_page_template(c, width, height, footer_data, left_col_data):
    """Draws the peripheral boundary and 6-box footer[cite: 3, 54, 85, 101]."""
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    
    box_width = (width - (2 * PAGE_MARGIN)) / 6
    info_column_x = PAGE_MARGIN + box_width 
    c.line(info_column_x, PAGE_MARGIN, info_column_x, height - PAGE_MARGIN)
    
    info_box_height = 80
    c.line(PAGE_MARGIN, height - PAGE_MARGIN - info_box_height, info_column_x, height - PAGE_MARGIN - info_box_height)
    
    for i in range(1, 6):
        x_pos = PAGE_MARGIN + (i * box_width)
        c.line(x_pos, PAGE_MARGIN, x_pos, footer_y)
    
    # Text Placement [cite: 54, 62, 85, 86, 100]
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 15, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 30, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 3, height - PAGE_MARGIN - 40, left_col_data['line3'].upper())

    labels = ["box1", "box2", "box3", "box4", "box5", "box6"]
    for i, label in enumerate(labels):
        x_center = PAGE_MARGIN + (i * box_width) + (box_width / 2)
        text_lines = footer_data[label].split('\n')
        for j, line in enumerate(text_lines):
            c.drawCentredString(x_center, footer_y - 15 - (j * 10), line.upper())

    return info_column_x

def process_terminal_drawing(df, fs_config, footer_data, left_col_data, page_size):
    buffer = io.BytesIO()
    selected_size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=selected_size)
    width, height = selected_size
    
    info_column_x = draw_page_template(c, width, height, footer_data, left_col_data)
    
    # --- OPTIMIZATION ENGINE ---
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows_grouped = df.groupby('Row ID')
    num_rows = len(rows_grouped)
    
    # Dynamically calculate Row Height to fill page vertically [cite: 3, 29, 49]
    available_height = height - PAGE_MARGIN - 150 - 80 # Minus headers/footers
    dynamic_row_height = max(140, available_height / num_rows) if num_rows > 0 else 160
    
    # Horizontal constraints
    max_draw_width = width - PAGE_MARGIN - info_column_x - SAFETY_OFFSET - 40
    
    y_current = height - 150
    for rid, group in rows_grouped:
        terminals = group.to_dict('records')
        n_terms = len(terminals)
        
        # Generatively calculate the optimal gap 
        optimal_gap = min(40, max_draw_width / n_terms) if n_terms > 1 else 40
        x_start = info_column_x + SAFETY_OFFSET + 20

        c.setFont("Helvetica-Bold", fs_config['row'])
        c.drawRightString(x_start - 30, y_current + 15, str(rid))

        for idx, term in enumerate(terminals):
            tx = x_start + (idx * optimal_gap)
            # Draw Terminal Symbol [cite: 2-7, 9, 13]
            c.setLineWidth(1)
            c.line(tx-3, y_current, tx-3, y_current+40); c.line(tx+3, y_current, tx+3, y_current+40)
            c.circle(tx, y_current+40, 3, stroke=1, fill=1); c.circle(tx, y_current, 3, stroke=1, fill=1)
            c.setFont("Helvetica-Bold", fs_config['term'])
            c.drawRightString(tx - 8, y_current + 17, str(term['Terminal ID']).zfill(2))

        # Optimized Grouping [cite: 4-12, 14-23]
        for type_key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terminals):
                txt = str(terminals[i][type_key])
                s_x = x_start + (i * optimal_gap)
                j = i
                while j < len(terminals) and str(terminals[j][type_key]) == txt:
                    e_x = x_start + (j * optimal_gap)
                    j += 1
                
                # Dynamic text scaling per group [cite: 2-8]
                max_txt_w = (e_x - s_x) + (optimal_gap * 0.5)
                f_size = fs_config['head' if is_h else 'foot']
                while stringWidth(txt, "Helvetica-Bold", f_size) > max_txt_w and f_size > 4:
                    f_size -= 0.5
                
                c.setFont("Helvetica-Bold", f_size)
                c.line(s_x-5, y_current+y_off, e_x+5, y_current+y_off)
                mid = (s_x + e_x) / 2
                if is_h:
                    c.line(s_x-5, y_current+y_off, s_x-5, y_current+y_off-5)
                    c.line(e_x+5, y_current+y_off, e_x+5, y_current+y_off-5)
                    c.line(mid, y_current+y_off, mid, y_current+y_off+5)
                    c.drawCentredString(mid, y_current+y_off+8, txt)
                else:
                    c.line(s_x-5, y_current+y_off, s_x-5, y_current+y_off+5)
                    c.line(e_x+5, y_current+y_off, e_x+5, y_current+y_off+5)
                    c.line(mid, y_current+y_off, mid, y_current+y_off-5)
                    c.drawCentredString(mid, y_current+y_off-12, txt)
                i = j
        y_current -= dynamic_row_height

    c.save(); buffer.seek(0)
    return buffer

# --- STREAMLIT INTERFACE ---
st.set_page_config(page_title="Railway Terminal Generative UI", layout="wide")
st.title("🚉 Generative Layout Optimizer")

with st.sidebar:
    with st.expander("🛠️ Page & Optimization Settings", expanded=True):
        page_size = st.selectbox("Page Size", ["A4", "A3"])
        fs_config = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}
    
    with st.expander("📝 Title Block Customization"):
        left_col = {'line1': st.text_input("Top Left Title", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
        footer = {f"box{i+1}": st.text_area(f"Box {i+1}", f"Info {i+1}", height=60) for i in range(6)}

st.subheader("Automated Terminal Sequencing")
df_input = pd.DataFrame([{"Row ID": "A", "Header": "DID HHG (3RD)", "Footer": "101-30C", "Terminal ID": "01"}])
edited_df = st.data_editor(df_input, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate Optimized Drawing"):
    pdf_buffer = process_terminal_drawing(edited_df, fs_config, footer, left_col, page_size)
    st.download_button("⬇️ Download PDF", data=pdf_buffer, file_name="Optimized_Signaling_Plan.pdf")