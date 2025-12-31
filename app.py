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
ROW_HEIGHT_SPACING = 140 # Increased spacing to accommodate larger symbols

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

# --- SYMBOL DRAWING FUNCTIONS (4X SIZE) ---

def draw_relay_symbol(c, x, y):
    """Draws a Relay box at 4x the original size (96x96)."""
    c.setLineWidth(1.2)
    # Original was rect(x-12, y+45, 24, 24). New is 4x.
    c.rect(x - 48, y + 45, 96, 96, stroke=1, fill=0)
    c.line(x - 48, y + 45, x + 48, y + 141) # Diagonal line
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x, y + 90, "RELAY")



def draw_charger_symbol(c, x, y):
    """Draws a Battery Charger symbol at 4x size."""
    c.setLineWidth(1.2)
    c.rect(x - 56, y + 45, 112, 80, stroke=1, fill=0)
    c.line(x - 56, y + 85, x + 56, y + 85) # Divider
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x, y + 105, "CHGR")
    c.drawCentredString(x, y + 60, "DC OUT")



def draw_fuse_symbol(c, x, y):
    """Draws a Fuse Block symbol at 4x size."""
    c.setLineWidth(1.2)
    c.rect(x - 32, y + 45, 64, 100, stroke=1, fill=0)
    # Scaled Bezier curve
    c.bezier(x-16, y+65, x+32, y+85, x-32, y+105, x+16, y+125)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x, y + 155, "FUSE")



[Image of an electrical fuse symbol]


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
    y_start, y_curr = height - 180, height - 180 # Adjusted for large symbols
    rows_on_page = 0
    
    draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
    
    for rid, group in df.groupby('Row ID', sort=False):
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        for chunk in chunks:
            if rows_on_page >= 5: # Reduced to 5 rows to ensure 4x symbols fit
                c.showPage()
                sheet_count += 1
                draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
                y_curr, rows_on_page = y_start, 0
            
            x_start = info_x + SAFETY_OFFSET + 20
            c.setFont("Helvetica-Bold", fs['row']); c.drawRightString(x_start - 30, y_curr + 15, str(rid))
            
            for idx, t in enumerate(chunk):
                tx = x_start + (idx * FIXED_GAP)
                func_name = str(t['Function']).upper()
                
                # MUTUALLY EXCLUSIVE DRAWING: Symbol OR Pin
                if "RELAY" in func_name:
                    draw_relay_symbol(c, tx, y_curr)
                elif "CHGR" in func_name:
                    draw_charger_symbol(c, tx, y_curr)
                elif "FUSE" in func_name:
                    draw_fuse_symbol(c, tx, y_curr)
                else:
                    c.setLineWidth(1)
                    c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                    c.circle(tx, y_curr+40, 3, fill=1); c.circle(tx, y_curr, 3, fill=1)
                
                # Always draw terminal number
                c.setFont("Helvetica-Bold", fs['term'])
                c.drawRightString(tx-8, y_curr+17, str(t['Terminal Number']).zfill(2))
            
            # Grouping Brackets (Increased top offset to 160 for 4x symbols)
            for key, is_h, y_off in [('Function', True, 160.0), ('Cable Detail', False, -13.5)]:
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
    with st.expander("📘 USER MANUAL", expanded=False):
        st.markdown("### Symbol Triggers")
        st.write("- **RELAY:** Large component box.")
        st.write("- **CHGR:** Battery charger block.")
        st.write("- **FUSE:** Fuse block symbol.")

    st.divider()
    st.header("⚙️ Page Setting")
    page_heading = st.text_input("Page Heading", "TERMINAL CHART / CTR PARTICULARS")
    with st.expander("📂 Footer Details"):
        f_vals = [st.text_input("Prep", "NOVALINE"), st.text_input("Chk1", "SSE/SIG"), 
                  st.text_input("Chk2", "ASTE/SIG"), st.text_input("Appr", "DY.CSTE"), 
                  st.text_input("CTR No", "CTR-01"), st.text_input("G-No", "G-05"), 
                  st.text_input("Stn", "STATION"), st.text_input("SIP", "SIP/2025"), "AUTO"]
    fs = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}

uploaded_file = st.file_uploader("Upload .txt file", type=["txt"])
if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    all_parsed = []
    for line in raw_text.splitlines():
        if line.strip():
            parsed = parse_fixed_format_multi_function(line.strip())
            if parsed: all_parsed.extend(parsed)
    if all_parsed: st.session_state.df = pd.DataFrame(all_parsed).reset_index(drop=True)

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Function": "RELAY", "Cable Detail": "N/A", "Terminal Number": "01"}])

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing"):
    pdf = process_drawing(st.session_state.df, fs, f_vals, page_heading)
    st.download_button("⬇️ Download PDF Drawing", data=pdf, file_name="CTR_Particulars.pdf")