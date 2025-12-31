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

def parse_txt_file(raw_text):
    """Parses tags and terminal data from the text file."""
    data_rows = []
    # Removed specific defaults (G-05, CTR-01, etc.)
    metadata = {
        "sheet": 1,
        "station": "",
        "location": "", 
        "sip": "",
        "heading": "TERMINAL CHART / CTR PARTICULARS"
    }

    for line in raw_text.splitlines():
        line = line.strip()
        if not line: continue
        
        upper_line = line.upper()
        if upper_line.startswith("SHEET:"):
            val = re.search(r'\d+', line)
            if val: metadata["sheet"] = int(val.group())
        elif upper_line.startswith("STATION:"):
            metadata["station"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("LOCATION:"):
            metadata["location"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("SIP:"):
            metadata["sip"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("HEADING:"):
            metadata["heading"] = line.split(":", 1)[1].strip()
        else:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
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
                        data_rows.append({
                            "Row ID": rid, "Function": func_text, 
                            "Cable Detail": cable_detail, "Terminal Number": str(i).zfill(2)
                        })
    return metadata, data_rows

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
    box_w = remaining_w / 7 
    dividers = [info_x + (i * box_w) for i in range(8)] 
    for x in dividers[:-1]: c.line(x, PAGE_MARGIN, x, footer_y)

    headers = [
        "PREPARED BY", "CHECKED BY", "CHECKED BY", "APPROVED BY", 
        "LOCATION NO / GOOMTY / RR", "STATION", "SIP", "SHEET NO."
    ]
    
    for i in range(8):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        
        c.setFont("Helvetica-Bold", 4.0 if i == 4 else 4.5)
        c.drawCentredString(x_c, footer_y - 12, headers[i])
        
        c.setFont("Helvetica", 6.5)
        val = f"{sheet_num:02}" if i == 7 else str(footer_values[i])
        lines = val.upper().split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_c, footer_y - 25 - (idx * 10), line)
    return info_x

def process_drawing(df, fs, footer_values, page_heading, start_sheet_no):
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    
    df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    info_x = PAGE_MARGIN + ((width - (2 * PAGE_MARGIN)) / 15)
    max_draw_w = width - info_x - SAFETY_OFFSET - 40
    terminals_per_row = int(max_draw_w // FIXED_GAP)
    
    current_sheet_val = start_sheet_no
    y_start, y_curr = height - 160, height - 160
    rows_on_page = 0
    
    draw_page_template(c, width, height, footer_values, current_sheet_val, page_heading)
    
    for rid, group in df.groupby('Row ID', sort=False):
        terms = group.to_dict('records')
        chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
        for chunk in chunks:
            if rows_on_page >= 6:
                c.showPage()
                current_sheet_val += 1 
                draw_page_template(c, width, height, footer_values, current_sheet_val, page_heading)
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
            
    c.save(); buffer.seek(0)
    return buffer, (current_sheet_val - start_sheet_no + 1), current_sheet_val

# --- STREAMLIT UI ---
st.set_page_config(page_title="CTR Generator Pro", layout="wide")
st.title("🚉 CTR Particular Generator")

# Initialize State with Empty Placeholders
if 'metadata' not in st.session_state:
    st.session_state.metadata = {"sheet": 1, "station": "", "location": "", "sip": "", "heading": ""}

with st.sidebar:
    st.header("🛠️ Control Panel")
    
    with st.expander("📖 DOCUMENTATION & TXT FORMAT", expanded=False):
        st.markdown("### **Header Metadata Tags**")
        st.code("""HEADING: MAIN PAGE TITLE
STATION: STATION NAME
LOCATION: LOCATION NO / GOOMTY / RR
SIP: SIP NUMBER
SHEET: START PAGE NO""", language="text")

    with st.expander("✒️ OFFICIAL NAMES FOR SIGNATURES", expanded=False):
        prep_by = st.text_input("Prepared By", "")
        chk_by1 = st.text_input("Checked By (SSE)", "")
        chk_by2 = st.text_input("Checked By (ASTE)", "")
        app_by = st.text_input("Approved By", "")

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("📂 Upload Drawing Content (.txt)", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    meta, rows = parse_txt_file(raw_text)
    
    if rows:
        st.session_state.metadata = meta
        st.session_state.df = pd.DataFrame(rows).reset_index(drop=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Station", meta['station'] if meta['station'] else "N/A")
        col2.metric("Location / RR", meta['location'] if meta['location'] else "N/A")
        col3.metric("Start Sheet", f"{meta['sheet']:02}")
        st.info(f"📑 **Active Heading:** {meta['heading']}")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"Row ID": "", "Function": "", "Cable Detail": "", "Terminal Number": "01"}])

st.markdown("### 📊 Data Review & Edit")
st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF Drawing", type="primary"):
    if not st.session_state.df.empty:
        m = st.session_state.metadata
        f_vals = [prep_by, chk_by1, chk_by2, app_by, m['location'], m['station'], m['sip'], "AUTO"]
        
        pdf_buffer, total_pages, last_sheet = process_drawing(
            st.session_state.df, 
            {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}, 
            f_vals, 
            m['heading'],
            m['sheet']
        )
        
        current_date = datetime.now().strftime("%d-%m-%Y")
        # Sanitize for filename
        clean_stn = m['station'].replace("/", "-") if m['station'] else "STN"
        clean_loc = m['location'].replace("/", "-") if m['location'] else "LOC"
        
        sheet_label = f"{m['sheet']:02}" if total_pages == 1 else f"{m['sheet']:02}-to-{last_sheet:02}"
        filename = f"{clean_loc}_{clean_stn}_SHEET-{sheet_label}_{current_date}.pdf"
        
        st.divider()
        st.download_button(
            label="📥 Download Finished PDF Drawing",
            data=pdf_buffer,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True
        )