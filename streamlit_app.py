import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
import re

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
            st.session_state.courses = pd.concat([st.session_state.courses, pd.DataFrame([{'Course': course or 'Untitled', 'Grade': grade, 'Credits': credits}])], ignore_index=True)

if mode == 'Transcript upload':
    up = st.sidebar.file_uploader('Upload Transcript (PDF, PNG, JPG)', type=['pdf','png','jpg','jpeg'])
    if up is not None:
        st.sidebar.success(f'Uploaded: {up.name}')
        text = st.sidebar.text_area('OCR/Text fallback input', height=120, placeholder='Paste extracted transcript text here if OCR is unavailable')
        if text:
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = re.split(r'\s{2,}|,|	', line)
                if len(parts) >= 3:
                    course, grade, credits = parts[0], parts[1].upper().strip(), parts[2]
                    try:
                        credits = float(re.findall(r'[0-9]+(?:\.[0-9]+)?', str(credits))[0])
                        rows.append({'Course': course, 'Grade': grade, 'Credits': credits})
                    except Exception:
                        pass
            if rows:
                st.session_state.courses = pd.DataFrame(rows)
                st.sidebar.success(f'Parsed {len(rows)} rows from pasted text.')
            else:
                st.sidebar.warning('No rows parsed. Use the manual entry table below to verify OCR output.')

mapping = SCALES[scale]
df = st.session_state.courses.copy()
edited = st.data_editor(df if not df.empty else pd.DataFrame([{'Course':'Sample Course','Grade':'A','Credits':3.0}]), use_container_width=True, num_rows='dynamic', key='course_editor')

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
c4.metric('Academic Standing', f'{standing} {('- ' + honors) if honors else ''}'.strip())

left, right = st.columns([1.35, 1])
with left:
    st.subheader('Course Overview')
    st.dataframe(calc[['Course','Grade','Credits','Points Earned']], use_container_width=True)
with right:
    st.subheader('Grade Distribution')
    if not calc.empty:
        dist = calc['Grade'].value_counts().reset_index()
        dist.columns = ['Grade','Count']
        st.altair_chart(alt.Chart(dist).mark_bar().encode(x='Grade:N', y='Count:Q', color='Grade:N'), use_container_width=True)
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
