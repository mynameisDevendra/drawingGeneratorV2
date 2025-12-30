import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
import re, io, json
import google.generativeai as genai # Required for Gemini level NLP

# --- API CONFIGURATION ---
# Replace with your actual API Key or set as an environment variable
GEMINI_API_KEY = "import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
import re, io, json
import google.generativeai as genai # Required for Gemini level NLP

# --- API CONFIGURATION ---
# Replace with your actual API Key or set as an environment variable
GEMINI_API_KEY = "import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
import re, io, json
import google.generativeai as genai # Required for Gemini level NLP

# --- API CONFIGURATION ---
# Replace with your actual API Key or set as an environment variable
GEMINI_API_KEY = "AIzaSyDoUG-Usx0LCR9RDDcwbGr0BU9u8Bw4qYA"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- GEMINI NLP INTERPRETER ---
def gemini_nlp_parser(user_prompt):
    """Uses Gemini to turn natural language into a structured terminal list."""
    system_instruction = """
    You are a railway signaling data assistant. Convert the user's text into a JSON list.
    Each item must have: "Row ID", "Header", "Footer", "Terminal ID".
    - Ensure Terminal ID is 2 digits (01, 02).
    - If a range is given (e.g. 1 to 5), create individual entries for each.
    - Default Header to 'SPARE' if not mentioned.
    Return ONLY a raw JSON list.
    """
    try:
        response = model.generate_content(f"{system_instruction}\n\nUser text: {user_prompt}")
        # Clean the response to ensure it's valid JSON
        json_str = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- PAGE LAYOUT TEMPLATE ---
def draw_page_template(c, width, height, footer_data, left_col_data):
    PAGE_MARGIN = 20
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
    
    # Left Column Text [cite: 52, 1-2]
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    # Footer Text [cite: 54, 89, 81, 85-86, 100]
    labels = ["box1", "box2", "box3", "box4", "box5", "box6"]
    for i, label in enumerate(labels):
        x_center = PAGE_MARGIN + (i * box_width) + (box_width / 2)
        lines = footer_data[label].split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_center, footer_y - 15 - (idx * 10), line.upper())

    return info_column_x

# --- DRAWING ENGINE ---
def draw_terminal(c, x, y, term_id, term_font_size):
    c.setLineWidth(1)
    c.line(x - 3, y, x - 3, y + 40) # [cite: 2-7]
    c.line(x + 3, y, x + 3, y + 40) # [cite: 2-7]
    c.setFillColorRGB(0, 0, 0)
    c.circle(x, y + 40, 3, stroke=1, fill=1) # [cite: 9]
    c.circle(x, y, 3, stroke=1, fill=1)      # [cite: 9]
    c.setFont("Helvetica-Bold", term_font_size)
    c.drawRightString(x - 8, y + 17, str(term_id).zfill(2)) 

def draw_bracket(c, x1, x2, y, text, is_header, f_size):
    c.setLineWidth(0.8)
    c.line(x1, y, x2, y)
    mid = (x1 + x2) / 2
    c.setFont("Helvetica-Bold", f_size)
    if is_header:
        c.line(x1, y, x1, y - 5); c.line(x2, y, x2, y - 5); c.line(mid, y, mid, y + 5)
        c.drawCentredString(mid, y + 10, str(text)) # [cite: 2-8]
    else:
        c.line(x1, y, x1, y + 5); c.line(x2, y, x2, y + 5); c.line(mid, y, mid, y - 5)
        c.drawCentredString(mid, y - (f_size + 8), str(text))

def process_drawing(df, fs, footer, left_col, page_size, gap):
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=size)
    width, height = size
    info_x = draw_page_template(c, width, height, footer, left_col)
    
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows = df.groupby('Row ID')
    y_current = height - 160
    # 1.5 cm Safety Offset 
    x_start = info_x + 42.5 + 25

    for rid, group in rows:
        terms = group.to_dict('records')
        c.setFont("Helvetica-Bold", fs['row'])
        c.drawRightString(x_start - 35, y_current + 15, str(rid))
        for idx, t in enumerate(terms):
            draw_terminal(c, x_start + (idx * gap), y_current, t['Terminal ID'], fs['term'])
        for key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terms):
                txt = str(terms[i][key])
                s_x = x_start + (i * gap); j = i
                while j < len(terms) and str(terms[j][key]) == txt:
                    e_x = x_start + (j * gap); j += 1
                draw_bracket(c, s_x - 5, e_x + 5, y_current + y_off, txt, is_h, fs['head' if is_h else 'foot'])
                i = j
        y_current -= 160
    c.save(); buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="Railway Gemini AI Designer", layout="wide")
st.title("🚉 Railway Terminal Gemini-Level NLP Designer")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Header", "Footer", "Terminal ID"])

with st.sidebar:
    st.header("Settings")
    with st.expander("🛠️ Page & Spacing"):
        p_size = st.selectbox("Size", ["A4", "A3"])
        manual_gap = st.slider("Terminal Gap", 20, 60, 35)
    with st.expander("📏 Fonts"):
        fs = {'head': st.number_input("Header", 8.0), 'foot': st.number_input("Footer", 7.0),
              'term': st.number_input("Terminal", 7.0), 'row': st.number_input("Row", 12.0)}
    with st.expander("📝 Left Column"):
        l_col = {'line1': st.text_input("Title", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
    with st.expander("📂 Footer"):
        f_data = {f"box{i+1}": st.text_area(f"Box {i+1}", f"Label {i+1}", height=60) for i in range(6)}

st.subheader("Interactive AI Assistant")
user_prompt = st.text_area("Talk to the drawing (Gemini NLP):", 
                           placeholder="Example: I need row B with 15 terminals for DID HHG (3RD) numbered 1 to 15. The footer should say 101-30C TO LOC-89.")

if st.button("🤖 Let Gemini Parse This"):
    with st.spinner("AI is interpreting your request..."):
        parsed_results = gemini_nlp_parser(user_prompt)
        if parsed_results:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(parsed_results)], ignore_index=True)
            st.success("Gemini has updated the terminal table!")

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF"):
    pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, manual_gap)
    st.download_button("⬇️ Download Drawing", data=pdf, file_name="Gemini_Signaling_Plan.pdf")" 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- GEMINI NLP INTERPRETER ---
def gemini_nlp_parser(user_prompt):
    """Uses Gemini to turn natural language into a structured terminal list."""
    system_instruction = """
    You are a railway signaling data assistant. Convert the user's text into a JSON list.
    Each item must have: "Row ID", "Header", "Footer", "Terminal ID".
    - Ensure Terminal ID is 2 digits (01, 02).
    - If a range is given (e.g. 1 to 5), create individual entries for each.
    - Default Header to 'SPARE' if not mentioned.
    Return ONLY a raw JSON list.
    """
    try:
        response = model.generate_content(f"{system_instruction}\n\nUser text: {user_prompt}")
        # Clean the response to ensure it's valid JSON
        json_str = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- PAGE LAYOUT TEMPLATE ---
def draw_page_template(c, width, height, footer_data, left_col_data):
    PAGE_MARGIN = 20
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
    
    # Left Column Text [cite: 52, 1-2]
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    # Footer Text [cite: 54, 89, 81, 85-86, 100]
    labels = ["box1", "box2", "box3", "box4", "box5", "box6"]
    for i, label in enumerate(labels):
        x_center = PAGE_MARGIN + (i * box_width) + (box_width / 2)
        lines = footer_data[label].split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_center, footer_y - 15 - (idx * 10), line.upper())

    return info_column_x

# --- DRAWING ENGINE ---
def draw_terminal(c, x, y, term_id, term_font_size):
    c.setLineWidth(1)
    c.line(x - 3, y, x - 3, y + 40) # [cite: 2-7]
    c.line(x + 3, y, x + 3, y + 40) # [cite: 2-7]
    c.setFillColorRGB(0, 0, 0)
    c.circle(x, y + 40, 3, stroke=1, fill=1) # [cite: 9]
    c.circle(x, y, 3, stroke=1, fill=1)      # [cite: 9]
    c.setFont("Helvetica-Bold", term_font_size)
    c.drawRightString(x - 8, y + 17, str(term_id).zfill(2)) 

def draw_bracket(c, x1, x2, y, text, is_header, f_size):
    c.setLineWidth(0.8)
    c.line(x1, y, x2, y)
    mid = (x1 + x2) / 2
    c.setFont("Helvetica-Bold", f_size)
    if is_header:
        c.line(x1, y, x1, y - 5); c.line(x2, y, x2, y - 5); c.line(mid, y, mid, y + 5)
        c.drawCentredString(mid, y + 10, str(text)) # [cite: 2-8]
    else:
        c.line(x1, y, x1, y + 5); c.line(x2, y, x2, y + 5); c.line(mid, y, mid, y - 5)
        c.drawCentredString(mid, y - (f_size + 8), str(text))

def process_drawing(df, fs, footer, left_col, page_size, gap):
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=size)
    width, height = size
    info_x = draw_page_template(c, width, height, footer, left_col)
    
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows = df.groupby('Row ID')
    y_current = height - 160
    # 1.5 cm Safety Offset 
    x_start = info_x + 42.5 + 25

    for rid, group in rows:
        terms = group.to_dict('records')
        c.setFont("Helvetica-Bold", fs['row'])
        c.drawRightString(x_start - 35, y_current + 15, str(rid))
        for idx, t in enumerate(terms):
            draw_terminal(c, x_start + (idx * gap), y_current, t['Terminal ID'], fs['term'])
        for key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terms):
                txt = str(terms[i][key])
                s_x = x_start + (i * gap); j = i
                while j < len(terms) and str(terms[j][key]) == txt:
                    e_x = x_start + (j * gap); j += 1
                draw_bracket(c, s_x - 5, e_x + 5, y_current + y_off, txt, is_h, fs['head' if is_h else 'foot'])
                i = j
        y_current -= 160
    c.save(); buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="Railway Gemini AI Designer", layout="wide")
st.title("🚉 Railway Terminal Gemini-Level NLP Designer")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Header", "Footer", "Terminal ID"])

with st.sidebar:
    st.header("Settings")
    with st.expander("🛠️ Page & Spacing"):
        p_size = st.selectbox("Size", ["A4", "A3"])
        manual_gap = st.slider("Terminal Gap", 20, 60, 35)
    with st.expander("📏 Fonts"):
        fs = {'head': st.number_input("Header", 8.0), 'foot': st.number_input("Footer", 7.0),
              'term': st.number_input("Terminal", 7.0), 'row': st.number_input("Row", 12.0)}
    with st.expander("📝 Left Column"):
        l_col = {'line1': st.text_input("Title", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
    with st.expander("📂 Footer"):
        f_data = {f"box{i+1}": st.text_area(f"Box {i+1}", f"Label {i+1}", height=60) for i in range(6)}

st.subheader("Interactive AI Assistant")
user_prompt = st.text_area("Talk to the drawing (Gemini NLP):", 
                           placeholder="Example: I need row B with 15 terminals for DID HHG (3RD) numbered 1 to 15. The footer should say 101-30C TO LOC-89.")

if st.button("🤖 Let Gemini Parse This"):
    with st.spinner("AI is interpreting your request..."):
        parsed_results = gemini_nlp_parser(user_prompt)
        if parsed_results:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(parsed_results)], ignore_index=True)
            st.success("Gemini has updated the terminal table!")

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF"):
    pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, manual_gap)
    st.download_button("⬇️ Download Drawing", data=pdf, file_name="Gemini_Signaling_Plan.pdf")" 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- GEMINI NLP INTERPRETER ---
def gemini_nlp_parser(user_prompt):
    """Uses Gemini to turn natural language into a structured terminal list."""
    system_instruction = """
    You are a railway signaling data assistant. Convert the user's text into a JSON list.
    Each item must have: "Row ID", "Header", "Footer", "Terminal ID".
    - Ensure Terminal ID is 2 digits (01, 02).
    - If a range is given (e.g. 1 to 5), create individual entries for each.
    - Default Header to 'SPARE' if not mentioned.
    Return ONLY a raw JSON list.
    """
    try:
        response = model.generate_content(f"{system_instruction}\n\nUser text: {user_prompt}")
        # Clean the response to ensure it's valid JSON
        json_str = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- PAGE LAYOUT TEMPLATE ---
def draw_page_template(c, width, height, footer_data, left_col_data):
    PAGE_MARGIN = 20
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
    
    # Left Column Text [cite: 52, 1-2]
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 20, left_col_data['line1'].upper())
    c.setFont("Helvetica", 6)
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 40, left_col_data['line2'].upper())
    c.drawString(PAGE_MARGIN + 5, height - PAGE_MARGIN - 50, left_col_data['line3'].upper())

    # Footer Text [cite: 54, 89, 81, 85-86, 100]
    labels = ["box1", "box2", "box3", "box4", "box5", "box6"]
    for i, label in enumerate(labels):
        x_center = PAGE_MARGIN + (i * box_width) + (box_width / 2)
        lines = footer_data[label].split('\n')
        for idx, line in enumerate(lines):
            c.drawCentredString(x_center, footer_y - 15 - (idx * 10), line.upper())

    return info_column_x

# --- DRAWING ENGINE ---
def draw_terminal(c, x, y, term_id, term_font_size):
    c.setLineWidth(1)
    c.line(x - 3, y, x - 3, y + 40) # [cite: 2-7]
    c.line(x + 3, y, x + 3, y + 40) # [cite: 2-7]
    c.setFillColorRGB(0, 0, 0)
    c.circle(x, y + 40, 3, stroke=1, fill=1) # [cite: 9]
    c.circle(x, y, 3, stroke=1, fill=1)      # [cite: 9]
    c.setFont("Helvetica-Bold", term_font_size)
    c.drawRightString(x - 8, y + 17, str(term_id).zfill(2)) 

def draw_bracket(c, x1, x2, y, text, is_header, f_size):
    c.setLineWidth(0.8)
    c.line(x1, y, x2, y)
    mid = (x1 + x2) / 2
    c.setFont("Helvetica-Bold", f_size)
    if is_header:
        c.line(x1, y, x1, y - 5); c.line(x2, y, x2, y - 5); c.line(mid, y, mid, y + 5)
        c.drawCentredString(mid, y + 10, str(text)) # [cite: 2-8]
    else:
        c.line(x1, y, x1, y + 5); c.line(x2, y, x2, y + 5); c.line(mid, y, mid, y - 5)
        c.drawCentredString(mid, y - (f_size + 8), str(text))

def process_drawing(df, fs, footer, left_col, page_size, gap):
    buffer = io.BytesIO()
    size = landscape(A3) if page_size == "A3" else landscape(A4)
    c = canvas.Canvas(buffer, pagesize=size)
    width, height = size
    info_x = draw_page_template(c, width, height, footer, left_col)
    
    df = df.dropna(subset=['Terminal ID'])
    df['sort_key'] = df['Terminal ID'].apply(lambda s: int(re.findall(r'\d+', str(s))[0]) if re.findall(r'\d+', str(s)) else 0)
    df = df.sort_values(by=['Row ID', 'sort_key'])
    
    rows = df.groupby('Row ID')
    y_current = height - 160
    # 1.5 cm Safety Offset 
    x_start = info_x + 42.5 + 25

    for rid, group in rows:
        terms = group.to_dict('records')
        c.setFont("Helvetica-Bold", fs['row'])
        c.drawRightString(x_start - 35, y_current + 15, str(rid))
        for idx, t in enumerate(terms):
            draw_terminal(c, x_start + (idx * gap), y_current, t['Terminal ID'], fs['term'])
        for key, is_h, y_off in [('Header', True, 53.5), ('Footer', False, -13.5)]:
            i = 0
            while i < len(terms):
                txt = str(terms[i][key])
                s_x = x_start + (i * gap); j = i
                while j < len(terms) and str(terms[j][key]) == txt:
                    e_x = x_start + (j * gap); j += 1
                draw_bracket(c, s_x - 5, e_x + 5, y_current + y_off, txt, is_h, fs['head' if is_h else 'foot'])
                i = j
        y_current -= 160
    c.save(); buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.set_page_config(page_title="Railway Gemini AI Designer", layout="wide")
st.title("🚉 Railway Terminal Gemini-Level NLP Designer")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Row ID", "Header", "Footer", "Terminal ID"])

with st.sidebar:
    st.header("Settings")
    with st.expander("🛠️ Page & Spacing"):
        p_size = st.selectbox("Size", ["A4", "A3"])
        manual_gap = st.slider("Terminal Gap", 20, 60, 35)
    with st.expander("📏 Fonts"):
        fs = {'head': st.number_input("Header", 8.0), 'foot': st.number_input("Footer", 7.0),
              'term': st.number_input("Terminal", 7.0), 'row': st.number_input("Row", 12.0)}
    with st.expander("📝 Left Column"):
        l_col = {'line1': st.text_input("Title", "COMPLETION DRAWING"), 'line2': "PCSTE'S REF NO.", 'line3': "7132/24"}
    with st.expander("📂 Footer"):
        f_data = {f"box{i+1}": st.text_area(f"Box {i+1}", f"Label {i+1}", height=60) for i in range(6)}

st.subheader("Interactive AI Assistant")
user_prompt = st.text_area("Talk to the drawing (Gemini NLP):", 
                           placeholder="Example: I need row B with 15 terminals for DID HHG (3RD) numbered 1 to 15. The footer should say 101-30C TO LOC-89.")

if st.button("🤖 Let Gemini Parse This"):
    with st.spinner("AI is interpreting your request..."):
        parsed_results = gemini_nlp_parser(user_prompt)
        if parsed_results:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(parsed_results)], ignore_index=True)
            st.success("Gemini has updated the terminal table!")

st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate PDF"):
    pdf = process_drawing(st.session_state.df, fs, f_data, l_col, p_size, manual_gap)
    st.download_button("⬇️ Download Drawing", data=pdf, file_name="Gemini_Signaling_Plan.pdf")