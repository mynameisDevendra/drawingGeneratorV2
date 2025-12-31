import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io
from datetime import datetime

# --- LAYOUT CONSTANTS ---
PAGE_MARGIN = 20
FIXED_GAP = 33
PAGE_SIZE = landscape(A3)
ROW_HEIGHT_SPACING = 145  # Increased spacing for 4x symbols

def parse_fixed_format_multi_function(text):
    """Parses TXT lines and distinguishes between Terminal Details and Cable Details."""
    new_rows = []
    try:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) < 2: return None
        rid = parts[0].upper()
        term_keywords = ["SPARE", "RESERVED", "NI", "E3", "BLOCK", "LINK", "RESERVE"]
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
                new_rows.append({"Row ID": rid, "Function": func_text, "Cable Detail": cable_detail, "Terminal Number": str(i).zfill(2)})
        return new_rows
    except: return None

# --- TECHNICAL SYMBOL LIBRARY (EXACT SPECIFICATIONS) ---

def draw_relay_symbol(c, x, y):
    """Relay: Rectangle with diagonal line (4x size)."""
    c.setLineWidth(1.2)
    c.rect(x - 45, y + 45, 90, 90, stroke=1, fill=0)
    c.line(x - 45, y + 45, x + 45, y + 135)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x, y + 90, "RELAY")



def draw_charger_symbol(c, x, y):
    """Charger: Rectangle with diagonal line and 110V/6V labels."""
    c.setLineWidth(1.2)
    c.rect(x - 50, y + 45, 100, 80, stroke=1, fill=0)
    c.line(x - 50, y + 45, x + 50, y + 125)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x - 40, y + 105, "110V")
    c.drawString(x + 15, y + 55, "6V")
    c.drawCentredString(x, y + 130, "CHARGER")



def draw_resistance_symbol(c, x, y):
    """Resistance: Rectangle with zig-zag pattern."""
    c.setLineWidth(1.2)
    c.rect(x - 30, y + 45, 60, 90, stroke=1, fill=0)
    p = c.beginPath()
    p.moveTo(x, y + 50)
    p.lineTo(x-15, y+60); p.lineTo(x+15, y+70); p.lineTo(x-15, y+80); p.lineTo(x, y+90)
    c.drawPath(p)
    c.drawCentredString(x, y + 140, "RES")



#[Image of an electrical resistor symbol in a circuit diagram]


def draw_choke_symbol(c, x, y):
    """Choke: Rectangle with three inductive loops."""
    c.setLineWidth(1.2)
    c.rect(x - 30, y + 45, 60, 90, stroke=1, fill=0)
    for i in range(3):
        c.arc(x-15, y+55+(i*15), x+15, y+75+(i*15), startAng=0, extent=180)
    c.drawCentredString(x, y + 140, "CHOKE")



def draw_fuse_s_symbol(c, x, y):
    """Fuse: S-type Bezier curve beside terminal path."""
    c.setLineWidth(1.2)
    p = c.beginPath()
    p.moveTo(x, y + 45)
    p.curveTo(x + 15, y + 55, x - 15, y + 75, x, y + 85)
    c.drawPath(p)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x, y + 95, "FUSE")



#[Image of an electrical fuse symbol]


# --- PDF ENGINE ---

def draw_page_template(c, width, height, footer_values, sheet_num, page_heading):
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, page_heading.upper())
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    info_x = PAGE_MARGIN + ((width - (2 * PAGE_MARGIN)) / 15)
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    dividers = [info_x + (i * ((width - info_x - PAGE_MARGIN) / 8)) for i in range(9)]
    for x in dividers[:-1]: c.line(x, PAGE_MARGIN, x, footer_y)
    return info_x

def process_drawing(df, fs, footer_values, page_heading):
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]))
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    sheet_count = 1
    y_start = height - 180
    y_curr, rows_on_page = y_start, 0
    info_x = draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
    terminals_per_row = int((width - info_x - 100) // FIXED_GAP)
    
    for rid, group in df.groupby('Row ID', sort=False):
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        for chunk in chunks:
            if rows_on_page >= 5: # Limit for large symbols
                c.showPage()
                sheet_count += 1
                draw_page_template(c, width, height, footer_values, sheet_count, page_heading)
                y_curr, rows_on_page = y_start, 0
            
            c.setFont("Helvetica-Bold", 12)
            c.drawRightString(info_x + 30, y_curr + 15, str(rid))
            
            for idx, t in enumerate(chunk):
                tx = info_x + 60 + (idx * FIXED_GAP)
                fn = str(t['Function']).upper()
                
                # DRAW SYMBOLS OR PINS (Mutually Exclusive)
                if any(x in fn for x in ["CHARGER", "CHGR"]):
                    draw_charger_symbol(c, tx, y_curr)
                elif "RELAY" in fn:
                    draw_relay_symbol(c, tx, y_curr)
                elif "RES" in fn:
                    draw_resistance_symbol(c, tx, y_curr)
                elif "CHOKE" in fn:
                    draw_choke_symbol(c, tx, y_curr)
                elif "FUSE" in fn:
                    draw_fuse_s_symbol(c, tx, y_curr)
                else:
                    c.setLineWidth(1)
                    c.line(tx-3, y_curr, tx-3, y_curr+40); c.line(tx+3, y_curr, tx+3, y_curr+40)
                    c.circle(tx, y_curr+40, 3, fill=1); c.circle(tx, y_curr, 3, fill=1)
                
                c.setFont("Helvetica-Bold", 7)
                c.drawCentredString(tx, y_curr + 15, str(t['Terminal Number']))

            # Grouping Brackets
            for key, is_h, y_off in [('Function', True, 160), ('Cable Detail', False, -15)]:
                i = 0
                while i < len(chunk):
                    txt = str(chunk[i][key]).upper().strip()
                    if not txt: i += 1; continue
                    start_i = i
                    while i < len(chunk) and str(chunk[i][key]).upper().strip() == txt: i += 1
                    end_i, i = i - 1, i
                    sx, ex = info_x + 60 + (start_i * FIXED_GAP), info_x + 60 + (end_i * FIXED_GAP)
                    c.line(sx-5, y_curr+y_off, ex+5, y_curr+y_off)
                    c.drawCentredString((sx+ex)/2, y_curr+y_off+(10 if is_h else -15), txt)

            y_curr -= ROW_HEIGHT_SPACING
            rows_on_page += 1
    c.save(); buffer.seek(0); return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Generator", layout="wide")
st.title("🚉 CTR Particular Generator (Pro Edition)")

with st.sidebar:
    with st.expander("📘 USER MANUAL & SYMBOL GUIDE", expanded=False):
        st.markdown("""
        ### Symbol Triggers (Case Insensitive)
        - **CHARGER / CHGR**: Rectangle with diagonal + 110V/6V labels.
        - **RELAY**: Square with diagonal coil indicator.
        - **FUSE**: S-type curve.
        - **RES**: Rectangle with Zig-Zag.
        - **CHOKE**: Rectangle with Inductor loops.
        
        ### TXT Protocol
        `RowID, Function [Start to End], CableDetail`
        """)
    st.divider()
    st.header("⚙️ Page Setting")
    page_heading = st.text_input("Page Heading", "TERMINAL CHART / CTR PARTICULARS")
    with st.expander("📂 Footer Details"):
        f_vals = [st.text_input("Prep", "NOVALINE"), st.text_input("Chk1", "SSE/SIG"), st.text_input("Chk2", "ASTE/SIG"), st.text_input("Appr", "DY.CSTE"), st.text_input("CTR", "CTR-01"), st.text_input("G-No", "G-05"), st.text_input("Stn", "STATION"), st.text_input("SIP", "SIP/2025")]

uploaded_file = st.file_uploader("Upload .txt file", type=["txt"])
if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    all_parsed = []
    for line in raw_text.splitlines():
        parsed = parse_fixed_format_multi_function(line.strip())
        if parsed: all_parsed.extend(parsed)
    if all_parsed: st.session_state.df = pd.DataFrame(all_parsed).reset_index(drop=True)

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "A", "Function": "CHARGER", "Cable Detail": "30C CABLE", "Terminal Number": "01"}])

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing"):
    pdf = process_drawing(st.session_state.df, None, f_vals, page_heading)
    st.download_button("⬇️ Download PDF Drawing", data=pdf, file_name="CTR_Technical_Drawing.pdf")