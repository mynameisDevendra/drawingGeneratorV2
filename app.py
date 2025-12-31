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

def parse_multi_sheet_txt(raw_text):
    """Parses a TXT file and groups data by Sheet based on the SHEET: tag."""
    sheets_data = []
    # Starting default metadata
    current_meta = {
        "sheet": 1, "station": "", "location": "", 
        "sip": "", "heading": "TERMINAL CHART / CTR PARTICULARS"
    }
    current_rows = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line: continue
        
        upper_line = line.upper()
        
        # DETECT NEW SHEET BREAK
        if upper_line.startswith("SHEET:"):
            # If we already have data from a previous sheet, save it before resetting
            if current_rows:
                sheets_data.append({"meta": current_meta.copy(), "rows": current_rows})
                current_rows = []
            
            val = re.search(r'\d+', line)
            if val: current_meta["sheet"] = int(val.group())
            
        elif upper_line.startswith("STATION:"):
            current_meta["station"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("LOCATION:"):
            current_meta["location"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("SIP:"):
            current_meta["sip"] = line.split(":", 1)[1].strip()
        elif upper_line.startswith("HEADING:"):
            current_meta["heading"] = line.split(":", 1)[1].strip()
        else:
            # Parse Terminal Data Rows
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                rid = parts[0].upper()
                term_keywords = ["SPARE", "RESERVED", "NI", "E3", "TERMINAL", "BLOCK", "LINK", "RESERVE"]
                last_part = parts[-1].upper()
                is_cable = not any(key in last_part for key in term_keywords)
                
                cable_detail = last_part if (is_cable and len(parts) >= 3) else ""
                middle_part = ",".join(parts[1:-1]) if cable_detail else ",".join(parts[1:])
                
                pattern = r'([^,\[]+)\[\s*(\d+)\s+to\s+(\d+)\s*\]'
                matches = re.findall(pattern, middle_part, re.I)
                
                for match in matches:
                    func_text = match[0].strip().upper()
                    start, end = int(match[1]), int(match[2])
                    for i in range(start, end + 1):
                        current_rows.append({
                            "Row ID": rid, "Function": func_text, 
                            "Cable Detail": cable_detail, "Terminal Number": str(i).zfill(2)
                        })
    
    # Save the final sheet in the file
    if current_rows:
        sheets_data.append({"meta": current_meta, "rows": current_rows})
    
    return sheets_data

def draw_page_template(c, width, height, footer_values, sheet_num, page_heading):
    c.setLineWidth(1.5)
    c.rect(PAGE_MARGIN, PAGE_MARGIN, width - (2 * PAGE_MARGIN), height - (2 * PAGE_MARGIN))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, page_heading.upper())
    
    footer_y = PAGE_MARGIN + 60
    c.line(PAGE_MARGIN, footer_y, width - PAGE_MARGIN, footer_y)
    total_footer_w = width - (2 * PAGE_MARGIN)
    info_x = PAGE_MARGIN + (total_footer_w / 15)
    c.line(info_x, PAGE_MARGIN, info_x, height - PAGE_MARGIN)
    
    remaining_w = total_footer_w - (total_footer_w / 15)
    box_w = remaining_w / 7 
    dividers = [info_x + (i * box_w) for i in range(8)] 
    for x in dividers[:-1]: c.line(x, PAGE_MARGIN, x, footer_y)

    headers = ["PREPARED BY", "CHECKED BY", "CHECKED BY", "APPROVED BY", "LOCATION NO / GOOMTY / RR", "STATION", "SIP", "SHEET NO."]
    for i in range(8):
        x_start = PAGE_MARGIN if i == 0 else dividers[i-1]
        x_end = dividers[i]
        x_c = (x_start + x_end) / 2
        c.setFont("Helvetica-Bold", 4.0 if i == 4 else 4.5)
        c.drawCentredString(x_c, footer_y - 12, headers[i])
        c.setFont("Helvetica", 6.5)
        val = f"{sheet_num:02}" if i == 7 else str(footer_values[i])
        c.drawCentredString(x_c, footer_y - 30, val.upper())
    return info_x

def process_multi_sheet_pdf(sheets_list, sig_data):
    buffer = io.BytesIO()
    width, height = PAGE_SIZE
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    fs = {'head': 8.0, 'foot': 7.0, 'term': 7.0, 'row': 12.0}

    for sheet in sheets_list:
        meta = sheet['meta']
        df = pd.DataFrame(sheet['rows'])
        df['sort_key'] = df['Terminal Number'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
        df = df.sort_values(by=['Row ID', 'sort_key'])

        f_vals = [sig_data['prep'], sig_data['chk1'], sig_data['chk2'], sig_data['app'], meta['location'], meta['station'], meta['sip'], "AUTO"]
        info_x = PAGE_MARGIN + ((width - (2 * PAGE_MARGIN)) / 15)
        terminals_per_row = int((width - info_x - SAFETY_OFFSET - 40) // FIXED_GAP)
        
        y_curr, rows_on_page = height - 160, 0
        current_sheet_no = meta['sheet']

        draw_page_template(c, width, height, f_vals, current_sheet_no, meta['heading'])

        for rid, group in df.groupby('Row ID', sort=False):
            terms = group.to_dict('records')
            chunks = [terms[i:i + terminals_per_row] for i in range(0, len(terms), terminals_per_row)]
            for chunk in chunks:
                if rows_on_page >= 6:
                    c.showPage()
                    current_sheet_no += 1
                    draw_page_template(c, width, height, f_vals, current_sheet_no, meta['heading'])
                    y_curr, rows_on_page = height - 160, 0
                
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
                        c.setLineWidth(0.8); c.line(s_x-5, y_curr+y_off, e_x+5, y_curr+y_off)
                        mid_x = (s_x+e_x)/2
                        c.setFont("Helvetica-Bold", fs['head' if is_h else 'foot'])
                        c.drawCentredString(mid_x, y_curr+y_off+(10 if is_h else -15), txt)
                
                y_curr -= ROW_HEIGHT_SPACING
                rows_on_page += 1
        c.showPage() 

    c.save()
    buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="Multi-Sheet CTR Generator", layout="wide")
st.title("🚉 Multi-Sheet CTR Generator")

with st.sidebar:
    st.header("🛠️ Control Panel")
    
    with st.expander("📖 DOCUMENTATION & TXT FORMAT", expanded=False):
        st.markdown("### **1. Sheet Break Logic**")
        st.info("The `SHEET:` tag acts as a mandatory page break. Use it to separate different Location Boxes or Goomties in the same file.")
        
        st.markdown("### **2. Required Example Format**")
        st.code("""SHEET: 01
LOCATION: LOC-01 / G-05
A, SPARE [01 to 10]
B, SIGNAL HR [01 to 05], 12C MAIN

SHEET: 05
LOCATION: LOC-02 / G-10
A, NI [01 to 04]
B, SPARE [01 to 10]""", language="text")
        
        st.markdown("---")
        st.markdown("### **3. Metadata Tags**")
        st.code("""HEADING: MAIN PAGE TITLE
STATION: STATION NAME
LOCATION: LOCATION NO / GOOMTY / RR
SIP: SIP NUMBER
SHEET: START PAGE NO""", language="text")

    with st.expander("✒️ OFFICIAL NAMES FOR SIGNATURES", expanded=False):
        sig_data = {
            "prep": st.text_input("Prepared By", ""),
            "chk1": st.text_input("Checked By (SSE)", ""),
            "chk2": st.text_input("Checked By (ASTE)", ""),
            "app": st.text_input("Approved By", "")
        }

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("📂 Upload Multi-Sheet Drawing Content (.txt)", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    sheets_data = parse_multi_sheet_txt(raw_text)
    
    if sheets_data:
        st.success(f"✅ Successfully detected {len(sheets_data)} sheet configurations in file.")
        
        # Overview Table
        summary = []
        for s in sheets_data:
            summary.append({
                "Start Sheet": s['meta']['sheet'],
                "Location": s['meta']['location'],
                "Station": s['meta']['station'],
                "Total Rows": len(pd.DataFrame(s['rows'])['Row ID'].unique())
            })
        st.table(summary)

        if st.button("🚀 Generate PDF for All Sheets", type="primary"):
            pdf_buffer = process_multi_sheet_pdf(sheets_data, sig_data)
            
            # Use current date for filename
            current_date = datetime.now().strftime("%d-%m-%Y")
            st.download_button(
                label="📥 Download Multi-Sheet PDF",
                data=pdf_buffer,
                file_name=f"Multi_Sheet_Drawing_{current_date}.pdf",
                mime="application/pdf",
                use_container_width=True
            )