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
    sheets_data = []
    current_meta = {
        "sheet": 1, "station": "", "location": "", 
        "sip": "", "heading": "TERMINAL CHART / CTR PARTICULARS"
    }
    current_rows = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line: continue
        upper_line = line.upper()
        
        if upper_line.startswith("SHEET:"):
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
        x_c = (PAGE_MARGIN if i == 0 else dividers[i-1] + dividers[i]) / 2 if i != 0 else (PAGE_MARGIN + info_x)/2
        if i > 0: x_c = (dividers[i-1] + dividers[i])/2
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
        y_curr, rows_on_page, current_sheet_no = height - 160, 0, meta['sheet']
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

if 'sheets_data' not in st.session_state:
    st.session_state.sheets_data = []

with st.sidebar:
    st.header("🛠️ Control Panel")
    with st.expander("📖 DOCUMENTATION & TXT FORMAT", expanded=False):
        st.code("""SHEET: 01\nLOCATION: LOC-01 / G-05\nA, SPARE [01 to 10]\n\nSHEET: 05\nLOCATION: LOC-02 / G-10\nA, NI [01 to 04]""", language="text")
    with st.expander("✒️ OFFICIAL NAMES FOR SIGNATURES", expanded=False):
        sig_data = {
            "prep": st.text_input("Prepared By", ""),
            "chk1": st.text_input("Checked By (SSE)", ""),
            "chk2": st.text_input("Checked By (ASTE)", ""),
            "app": st.text_input("Approved By", "")
        }

uploaded_file = st.file_uploader("📂 Upload Multi-Sheet Drawing Content (.txt)", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    st.session_state.sheets_data = parse_multi_sheet_txt(raw_text)
    st.success(f"✅ Detected {len(st.session_state.sheets_data)} sheet configurations.")

if st.session_state.sheets_data:
    st.markdown("### 📊 Data Preview & Edit")
    
    # Selector for which sheet to view/edit
    sheet_names = [f"Sheet {s['meta']['sheet']}: {s['meta']['location']}" for s in st.session_state.sheets_data]
    selected_sheet_idx = st.selectbox("Select Sheet to Preview/Edit", range(len(sheet_names)), format_func=lambda i: sheet_names[i])
    
    # Edit the selected sheet's dataframe
    current_df = pd.DataFrame(st.session_state.sheets_data[selected_sheet_idx]['rows'])
    edited_df = st.data_editor(current_df, num_rows="dynamic", use_container_width=True, key=f"editor_{selected_sheet_idx}")
    
    # Update state with edits
    st.session_state.sheets_data[selected_sheet_idx]['rows'] = edited_df.to_dict('records')

    # Excel Export Link
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for i, s in enumerate(st.session_state.sheets_data):
            pd.DataFrame(s['rows']).to_excel(writer, sheet_name=f"Sheet_{s['meta']['sheet']}", index=False)
    st.download_button(label="📥 Download All Tables as Excel", data=output.getvalue(), file_name="Parsed_Terminal_Data.xlsx", mime="application/vnd.ms-excel")

    st.divider()

    if st.button("🚀 Generate PDF for All Sheets", type="primary", use_container_width=True):
        pdf_buffer = process_multi_sheet_pdf(st.session_state.sheets_data, sig_data)
        st.download_button(label="📥 Download Multi-Sheet PDF", data=pdf_buffer, file_name=f"Multi_Sheet_Drawing_{datetime.now().strftime('%d-%m-%Y')}.pdf", mime="application/pdf", use_container_width=True)