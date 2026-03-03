import streamlit as st
import pandas as pd
import re

# 1. Page Config
st.set_page_config(page_title="Abra FHSIS Dashboard", layout="wide")

if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Resilient Period Extraction
def get_period(text):
    text = text.upper()
    periods = {
        "JAN": "January", "FEB": "February", "MAR": "March", "APR": "April", 
        "MAY": "May", "JUN": "June", "JUL": "July", "AUG": "August", 
        "SEP": "September", "OCT": "October", "NOV": "November", "DEC": "December",
        "Q1": "1st Quarter", "Q2": "2nd Quarter", "Q3": "3rd Quarter", "Q4": "4th Quarter",
        "ELIG": "Eligible Pop", "2025": "Annual 2025"
    }
    for key, val in periods.items():
        if key in text: return val
    return "Other Period"

# 3. Processing Engine
def process_rhu_csv(file):
    filename = file.name
    # Load CSV
    df = pd.read_csv(file, header=None)
    
    # Locate "Area"
    area_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            area_idx = i
            break
    if area_idx == -1: return pd.DataFrame()

    # Get Indicators (usually at area_idx) and Sex (usually at area_idx + 2)
    header_row = df.iloc[area_idx].fillna(method='ffill').astype(str).str.strip()
    sex_row = df.iloc[area_idx + 2].fillna('').astype(str).str.strip().str.title()
    
    # Filter data for Abra
    data = df.iloc[area_idx + 3:].copy()
    data.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sex_row)]
    
    # Rename Area Column
    area_col = [c for c in data.columns if 'area' in str(c).lower()][0]
    data = data.rename(columns={area_col: 'Area'})
    
    abra_rhus = ['Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 'Tayum', 'Tineg', 'Tubo', 'Villaviciosa']
    data['Area'] = data['Area'].astype(str).str.strip()
    data = data[data['Area'].isin(abra_rhus)]

    # Pivot to Long Format
    long = data.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    long = long[long['Metric'].str.contains('\|', na=False)]
    if long.empty: return pd.DataFrame()

    long[['Indicator', 'Sex']] = long['Metric'].str.split('|', expand=True)
    long['Count'] = pd.to_numeric(long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    final = long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    final['Month'] = get_period(filename)
    final['Source'] = filename
    return final

# 4. Sidebar Upload
with st.sidebar:
    st.header("📂 Data Controller")
    st.write("Upload the FHSIS CSV files for Abra RHUs.")
    files = st.file_uploader("Drop CSVs here", accept_multiple_files=True, type=['csv'])
    
    if st.button("🚀 Consolidate & Generate Charts", type="primary"):
        if files:
            all_dfs = []
            for f in files:
                res = process_rhu_csv(f)
                if not res.empty: all_dfs.append(res)
            
            if all_dfs:
                st.session_state.master_db = pd.concat(all_dfs, ignore_index=True)
                st.success("Analysis Ready!")
        else:
            st.warning("Please upload files first.")

# 5. Main Dashboard (1 Chart/Table per Indicator)
st.title("FHSIS Priority 1: Immunization (Abra RHU Level)")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Month Filter for the whole dashboard
    all_months = sorted(db['Month'].unique())
    selected_month = st.select_slider("Select Reporting Period to View:", options=all_months)
    
    # Filter DB by month
    month_data = db[db['Month'] == selected_month]
    
    # Get unique indicators
    indicators = sorted(month_data['Indicator'].unique())
    
    # Iterate and create one section per indicator
    for ind in indicators:
        with st.container():
            st.divider()
            st.subheader(f"💉 {ind}")
            
            # Filter for specific indicator
            ind_data = month_data[month_data['Indicator'] == ind].copy()
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Bar Chart
                st.write("**RHU Accomplishment (Male vs Female)**")
                st.bar_chart(ind_data.set_index('Area')[['Male', 'Female']])
            
            with col2:
                # Summary Table
                st.write("**Top Performing RHUs**")
                top_rhus = ind_data.sort_values(by='Total', ascending=False)[['Area', 'Total']].head(5)
                st.table(top_rhus)
                
                # Total Accomplishment Metric
                total_val = int(ind_data['Total'].sum())
                st.metric("Total Abra Count", f"{total_val:,}")

    # Export Section
    st.divider()
    csv = db.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Consolidated Database (Fact Table)", csv, "Abra_Imm_Master_FactTable.csv", "text/csv")

else:
    st.info("👈 Please upload your 2025 Immunization CSVs in the sidebar to generate the automated indicators.")
