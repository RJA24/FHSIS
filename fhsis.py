import streamlit as st
import pandas as pd
import re

# 1. Page Configuration
st.set_page_config(page_title="Abra FHSIS Command Center", layout="wide")

# Initialize Session State
if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Resilient Chronological Period Mapping
def get_period_label(text):
    text = str(text).upper()
    mapping = {
        "JAN": "01-January", "FEB": "02-February", "MAR": "03-March", 
        "APR": "04-April", "MAY": "05-May", "JUN": "06-June", 
        "JUL": "07-July", "AUG": "08-August", "SEP": "09-September", 
        "OCT": "10-October", "NOV": "11-November", "DEC": "12-December",
        "Q1": "Q1-First Quarter", "Q2": "Q2-Second Quarter", 
        "Q3": "Q3-Third Quarter", "Q4": "Q4-Fourth Quarter",
        "2025": "Annual 2025", "ELIG": "Eligible Population"
    }
    for key, val in mapping.items():
        if key in text:
            return val
    return "99-Other"

# 3. Enhanced Processing Logic
def process_fhsish_file(file):
    filename = file.name
    try:
        if filename.lower().endswith('.xlsx'):
            df = pd.read_excel(file, header=None)
        else:
            df = pd.read_csv(file, header=None)
    except Exception as e:
        st.error(f"Could not read {filename}: {e}")
        return pd.DataFrame()
    
    # Step 1: Find the "Area" row
    area_row_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            area_row_idx = i
            break
    
    if area_row_idx == -1:
        return pd.DataFrame()

    # Step 2: Extract Headers (Row 5) and Sex Subheaders (Row 7)
    header_row = df.iloc[area_row_idx].ffill().astype(str).str.replace('\n', ' ').str.strip()
    
    # Sex sub-header row is 2 rows below Area
    sex_row_idx = area_row_idx + 2
    if sex_row_idx >= len(df): return pd.DataFrame()
    
    sex_row = df.iloc[sex_row_idx].fillna('').astype(str).str.strip().str.title()
    
    # Step 3: Combine Header + Sex and filter for Abra RHUs
    data = df.iloc[sex_row_idx + 1:].copy()
    # Logic: Only tag columns that have Male, Female, or Total subheaders
    data.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sex_row)]
    
    area_col_candidates = [c for c in data.columns if 'area' in str(c).lower()]
    if not area_col_candidates: return pd.DataFrame()
    data = data.rename(columns={area_col_candidates[0]: 'Area'})
    
    abra_rhus = [
        'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
        'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
        'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
        'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
        'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
    ]
    data['Area'] = data['Area'].astype(str).str.strip()
    data = data[data['Area'].isin(abra_rhus)]

    # Step 4: Normalize to Long Format
    long = data.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # This filter explicitly excludes the "Eligible Pop" numbers next to Area
    long = long[long['Metric'].str.contains('\|', na=False)]
    if long.empty: return pd.DataFrame()

    long[['Indicator', 'Sex']] = long['Metric'].str.split('|', expand=True)
    long['Count'] = pd.to_numeric(long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Step 5: Final Pivot
    final = long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    for col in ['Male', 'Female', 'Total']:
        if col not in final.columns: final[col] = 0
            
    final['Period'] = get_period_label(filename)
    final['Source'] = filename
    return final

# 4. Sidebar Controller
with st.sidebar:
    st.header("📂 Data Entry")
    st.info("Upload 2025 Immunization Files.")
    files = st.file_uploader("Drop Files", accept_multiple_files=True, type=['csv', 'xlsx'])
    
    if st.button("🚀 Build Dashboard", type="primary"):
        if files:
            all_data = []
            num_files = len(files)
            progress = st.progress(0)
            for i, f in enumerate(files):
                res = process_fhsish_file(f)
                if not res.empty: all_data.append(res)
                progress.progress((i + 1) / num_files) # Fixed divisor bug
            
            if all_data:
                st.session_state.master_db = pd.concat(all_data, ignore_index=True)
                st.success("Analysis Ready!")
            else:
                st.error("No accomplishment data found in those templates.")

# 5. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra RHU Level)")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Safe Slider Logic to prevent RangeError
    periods = sorted(db['Period'].unique())
    if len(periods) > 1:
        selected_period = st.select_slider("Select Reporting Month/Period:", options=periods)
    elif len(periods) == 1:
        selected_period = periods[0]
        st.info(f"Viewing data for: {selected_period}")
    else:
        st.error("No period data found.")
        st.stop()
    
    view_data = db[db['Period'] == selected_period]
    indicators = sorted(view_data['Indicator'].unique())
    
    if not indicators:
        st.warning("No indicators found for this period.")
    else:
        for ind in indicators:
            with st.container():
                st.divider()
                st.subheader(f"💉 {ind}")
                ind_df = view_data[view_data['Indicator'] == ind].copy()
                
                # Check if data exists for this specific indicator to prevent chart crash
                if not ind_df.empty and ind_df['Total'].sum() > 0:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write("**Performance Breakdown (Male vs Female)**")
                        plot_data = ind_df.set_index('Area')[['Male', 'Female']]
                        st.bar_chart(plot_data)
                    with col2:
                        st.write("**Leaderboard**")
                        top_5 = ind_df.sort_values(by='Total', ascending=False)[['Area', 'Total']].head(5)
                        st.table(top_5)
                        total_abra = int(ind_df['Total'].sum())
                        st.metric(f"Total {ind} (Abra)", f"{total_abra:,}")
                else:
                    st.info(f"No accomplishments recorded for {ind} in {selected_period}.")

    # Export
    st.divider()
    csv = db.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Power BI Fact Table", csv, "Abra_Imm_2025_Master.csv", "text/csv")
else:
    st.warning("👈 Please upload your 2025 Immunization files in the sidebar to begin.")
