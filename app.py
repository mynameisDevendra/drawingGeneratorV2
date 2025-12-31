import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
import re
import io
from datetime import datetime

# --- UI CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="CTR Generator Pro", layout="wide")

st.markdown("""
    <style>
    div[data-baseweb="select"] { cursor: pointer !important; }
    .stSelectbox div { cursor: pointer !important; }
    </style>
    """, unsafe_allow_html=True)

# --- SAMPLE FILE CONTENT ---
SAMPLE_CONTENT = """HEADING: SAMPLE TERMINAL CHART
STATION: NEW DELHI
LOCATION: LOC-01 / G-05
SIP: SIP/NDLS/2024/01
SHEET: 01

A, SIGNAL HR [01 to 05], 12C MAIN
A, SPARE [06 to 10]
B, POINT NWKR [01 to 04], 19C TAIL
B, NI [05 to 08]

SHEET: 05
LOCATION: LOC-02 / RR-NORTH
A, TRACK CIRCUIT [01 to 06], 2C CABLE
A, SPARE [07 to 10]
"""

# --- HELPER FUNCTIONS ---
def validate_terminal_sequences(sheets_data):
    errors = []
    for s_idx, sheet in enumerate(sheets_data):
        df = pd.DataFrame(sheet['rows'])
        if df.empty: continue
        df['num'] = pd.to_numeric(df['Terminal Number'], errors='coerce')
        for rid, group in df.groupby('Row ID'):
            sorted_nums = sorted(group['num'].dropna().unique())
            if not sorted_nums: continue
            for i in range(len(sorted_nums) - 1):
                if sorted_nums[i+1] != sorted_nums[i] + 1:
                    missing = list(range(int(sorted_nums[i]) + 1, int(sorted_nums[i+1])))
                    missing_str = ", ".join([str(m).zfill(2) for m in missing])
                    errors.append({
                        "Sheet/Location": sheet['meta']['location'] or f"Sheet {s_idx+1}",
                        "Row": rid,
                        "Error": f"Gap: Missing {missing_str} (Between {int(sorted_nums[i]):02}-{int(sorted_nums[i+1]):02})"
                    })
    return errors

def draw_curly_bracket(c, x1, x2, y, is_top=True):
    mid_x = (x1 + x2) / 2
    height = 10 if is_top else -10
    peak = y + height
    c.setLineWidth(0.8)
    p = c.beginPath()
    p.moveTo(x1, y)
    c1x, c1y = x1 + (mid_x - x1) * 0.2, y
    c2x, c2y = x1 + (mid_x - x1) * 0.5, peak
    p.curveTo(c1x, c1y, c2x, c2y, mid_x, peak)
    c3x, c3y = x2 - (x2 - mid_x) * 0.5, peak
    c4x, c4y = x2 - (x2 - mid_x) * 0.2, y
    p.curveTo(c3x, c3y, c4x, c4y, x2, y)
    c.drawPath(p)

# ... [parse_multi_sheet_txt, draw_page_template, process_multi_sheet_pdf logic remains unchanged] ...

# --- STREAMLIT SIDEBAR ---
with st.sidebar:
    st.header("📂 Resources & Settings")
    
    # DOWNLOAD SAMPLE BUTTON
    st.subheader("1. Sample Template")
    st.download_button(
        label="📥 Download Sample TXT File",
        data=SAMPLE_CONTENT,
        file_name="sample_ctr_input.txt",
        mime="text/plain",
        help="Download this to see how to format your input data correctly.",
        use_container_width=True
    )
    
    st.divider()
    
    # DOCUMENTATION
    with st.expander("📘 Format Instructions", expanded=False):
        st.markdown("**Tags:** `HEADING:`, `STATION:`, `LOCATION:`, `SHEET:`")
        st.markdown("**Data:** `Row, Function [Start to End], CableDetail`")
        st.info("Ensure No Gaps in Terminal Numbers (e.g., 1 to 4 then 5 to 8).")

    # SIGNATURES
    with st.expander("✒️ Signature Details", expanded=False):
        sig_data = {
            "prep": st.text_input("Prepared By", "JE/SIG"),
            "chk1": st.text_input("Checked By (SSE)", "SSE/SIG"),
            "chk2": st.text_input("Checked By (ASTE)", "ASTE"),
            "app": st.text_input("Approved By", "DSTE")
        }

# --- MAIN INTERFACE ---
st.title("🚉 Multi-Sheet CTR Generator")

uploaded_file = st.file_uploader("📂 Upload Your Drawing Content (.txt)", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.getvalue().decode("utf-8")
    st.session_state.sheets_data = parse_multi_sheet_txt(raw_text)

if 'sheets_data' in st.session_state and st.session_state.sheets_data:
    st.markdown("### 📊 Data Preview & Validation")
    
    # Sheet Selector
    sheet_names = [f"Sheet {s['meta']['sheet']}: {s['meta']['location']}" for s in st.session_state.sheets_data]
    selected_sheet_idx = st.selectbox("Select Sheet to Edit", range(len(sheet_names)), format_func=lambda i: sheet_names[i])
    
    # Data Editor
    current_df = pd.DataFrame(st.session_state.sheets_data[selected_sheet_idx]['rows'])
    edited_df = st.data_editor(current_df, num_rows="dynamic", use_container_width=True, key=f"editor_{selected_sheet_idx}")
    st.session_state.sheets_data[selected_sheet_idx]['rows'] = edited_df.to_dict('records')
    
    # Sequence Check
    seq_errors = validate_terminal_sequences(st.session_state.sheets_data)
    if seq_errors:
        st.error("⚠️ Sequence Errors Found!")
        st.table(seq_errors)
    else:
        st.success("✅ Terminal sequences are continuous.")

    # PDF Generation
    if st.button("🚀 Generate Final PDF Drawing", type="primary", use_container_width=True):
        pdf_buffer = process_multi_sheet_pdf(st.session_state.sheets_data, sig_data)
        st.download_button(label="📥 Download PDF", data=pdf_buffer, file_name=f"CTR_Output_{datetime.now().strftime('%d%m%Y')}.pdf", mime="application/pdf", use_container_width=True)