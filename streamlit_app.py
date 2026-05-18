import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
import re
import tempfile

st.set_page_config(page_title='CGPA Dashboard 2026', layout='wide')

SCALES = {
    '4.0': {'A+': 4.0, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7, 'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D+': 1.3, 'D': 1.0, 'F': 0.0},
    '5.0': {'A': 5.0, 'B': 4.0, 'C': 3.0, 'D': 2.0, 'E': 1.0, 'F': 0.0},
    '10.0': {'O': 10.0, 'S': 9.0, 'A': 8.0, 'B': 7.0, 'C': 6.0, 'D': 5.0, 'E': 4.0, 'F': 0.0}
}
HONORS = [(3.90,4.00,'Exceptional','Summa Cum Laude'),(3.70,3.89,'Excellent','Magna Cum Laude'),(3.50,3.69,'Very Good','Cum Laude'),(3.00,3.49,'Good',"Dean's List"),(2.50,2.99,'Satisfactory',''),(2.00,2.49,'Average',''),(0.00,1.99,'Below Average','Academic Probation Warning')]

st.title('CGPA Calculator & Academic Dashboard 2026')
scale = st.sidebar.selectbox('Grading scale', ['4.0','5.0','10.0'])
mode = st.sidebar.radio('Input mode', ['Manual entry','Transcript upload'])

if 'courses' not in st.session_state:
    st.session_state.courses = pd.DataFrame(columns=['Course','Grade','Credits'])

with st.sidebar.expander('Add course row', expanded=True):
    with st.form('add_course', clear_on_submit=True):
        course = st.text_input('Course name')
        grade = st.text_input('Grade').upper().strip()
        credits = st.number_input('Credit hours', min_value=0.0, step=0.5, format='%.2f')
        if st.form_submit_button('Add Course Row') and grade and credits > 0:
            st.session_state.courses = pd.concat(
                [st.session_state.courses, pd.DataFrame([{'Course': course or 'Untitled', 'Grade': grade, 'Credits': credits}])],
                ignore_index=True
            )

def parse_ocr_text(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'\s{2,}|,|\t', line)
        if len(parts) >= 3:
            course = parts[0].strip()
            grade = parts[1].upper().strip()
            credit_part = parts[2]
            m = re.findall(r'[0-9]+(?:\.[0-9]+)?', str(credit_part))
            if m:
                try:
                    rows.append({'Course': course, 'Grade': grade, 'Credits': float(m[0])})
                except Exception:
                    pass
    return pd.DataFrame(rows)

if mode == 'Transcript upload':
    up = st.sidebar.file_uploader('Upload Transcript (PDF, PNG, JPG)', type=['pdf','png','jpg','jpeg'])
    if up is not None:
        st.sidebar.success(f'Uploaded: {up.name}')
        submitted = st.sidebar.button('Run OCR / Extract & Calculate')
        if submitted:
            extracted = pd.DataFrame()
            file_suffix = Path(up.name).suffix.lower()

            try:
                if file_suffix == '.pdf':
                    try:
                        import pdfplumber
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                            tmp.write(up.getbuffer())
                            tmp_path = tmp.name

                        text_chunks = []
                        with pdfplumber.open(tmp_path) as pdf:
                            for page in pdf.pages:
                                txt = page.extract_text() or ''
                                if txt:
                                    text_chunks.append(txt)

                        extracted = parse_ocr_text('\n'.join(text_chunks))
                    except Exception:
                        st.sidebar.warning('PDF text extraction failed. Paste OCR text below for parsing.')
                else:
                    try:
                        from PIL import Image
                        import pytesseract
                        image = Image.open(up)
                        txt = pytesseract.image_to_string(image)
                        extracted = parse_ocr_text(txt)
                    except Exception:
                        st.sidebar.warning('Image OCR failed. Paste OCR text below for parsing.')
            except Exception:
                st.sidebar.warning('Automatic extraction failed.')

            if extracted.empty:
                fallback = st.sidebar.text_area(
                    'Paste OCR/Text fallback input',
                    height=160,
                    placeholder='Course  Grade  Credits\nMathematics  A  3\n...'
                )
                if fallback.strip():
                    extracted = parse_ocr_text(fallback)

            if not extracted.empty:
                st.session_state.courses = extracted
                st.sidebar.success(f'Parsed {len(extracted)} rows and loaded into the dashboard.')
            else:
                st.sidebar.warning('No rows parsed. Please verify file quality or use manual entry.')

mapping = SCALES[scale]
df = st.session_state.courses.copy()
if df.empty:
    df = pd.DataFrame([{'Course':'Sample Course','Grade':'A','Credits':3.0}])

edited = st.data_editor(df, use_container_width=True, num_rows='dynamic', key='course_editor')

calc = edited.copy()
calc['Grade'] = calc['Grade'].astype(str).str.upper().str.strip()
calc['Grade Point'] = calc['Grade'].map(mapping)
calc['Points Earned'] = calc['Grade Point'] * calc['Credits']
invalid = calc[calc['Grade Point'].isna()].copy()
calc = calc.dropna(subset=['Grade Point'])

if not calc.empty:
    total_credits = float(calc['Credits'].sum())
    total_qp = float(calc['Points Earned'].sum())
    cgpa = round(total_qp / total_credits, 2) if total_credits else 0.0
else:
    total_credits = total_qp = cgpa = 0.0

standing, honors = 'N/A', ''
if scale == '4.0':
    for lo, hi, s, h in HONORS:
        if lo <= cgpa <= hi:
            standing, honors = s, h
            break

c1, c2, c3, c4 = st.columns(4)
c1.metric('Final CGPA', f'{cgpa:.2f}')
c2.metric('Total Credits Earned', f'{total_credits:.2f}')
c3.metric('Total Quality Points', f'{total_qp:.2f}')
c4.metric('Academic Standing', f'{standing} {("- " + honors) if honors else ""}'.strip())

left, right = st.columns([1.35, 1])
with left:
    st.subheader('Course Overview')
    st.dataframe(calc[['Course','Grade','Credits','Points Earned']], use_container_width=True)
with right:
    st.subheader('Grade Distribution')
    if not calc.empty:
        dist = calc['Grade'].value_counts().reset_index()
        dist.columns = ['Grade','Count']
        st.altair_chart(
            alt.Chart(dist).mark_bar().encode(x='Grade:N', y='Count:Q', color='Grade:N'),
            use_container_width=True
        )
    else:
        st.info('No valid grade data yet.')

if not invalid.empty:
    st.warning('Some rows contain unrecognized grades and were excluded from CGPA calculation.')
    st.dataframe(invalid[['Course','Grade','Credits']], use_container_width=True)

report = pd.DataFrame([
    {'Metric':'Scale','Value':scale},
    {'Metric':'Final CGPA','Value':f'{cgpa:.2f}'},
    {'Metric':'Total Credits','Value':f'{total_credits:.2f}'},
    {'Metric':'Total Quality Points','Value':f'{total_qp:.2f}'},
    {'Metric':'Academic Standing','Value':f'{standing} {honors}'.strip()}
])
st.subheader('Printable Report')
st.dataframe(report, use_container_width=True)

csv = calc[['Course','Grade','Credits','Points Earned']].to_csv(index=False).encode('utf-8')
st.download_button('Download report CSV', csv, 'cgpa_report.csv', 'text/csv')
