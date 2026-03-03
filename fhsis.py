import streamlit as st
import pandas as pd
import re

# 1. Page Configuration
st.set_page_config(page_title="Abra FHSIS Command Center", layout="wide")

if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Resilient Month/Quarter Mapping
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
def process_fhsish_csv(file):
    filename = file.name
    # Try to read with different encodings if needed
    try:
        df = pd.read_csv(file, header=None)
    except:
        return pd.DataFrame()
    
    # Find row with "Area"
    area_row_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            area_row_idx = i
            break
    
    if area_row_idx == -1:
        return pd.DataFrame()

    # Identify Headers and Sex Subheaders
    # Indicators are usually in the Area row (idx)
    # Male/Female are usually 2 rows below (idx + 2)
    header_row = df.iloc[area_row_idx].fillna(method='ffill').astype(str).str.strip()
    sex_row = df.iloc[area_row_idx + 2].fillna('').astype(str).str.strip().str.title()
    
    # Filter for Abra RHUs
    data = df.iloc[area_row_idx + 3:].copy()
    data.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sex_row)]
    
    # Rename Area
    area_col = [c for c in data.columns if 'area' in str(c).lower()][0]
    data = data.rename(columns={area_col: 'Area'})
    
    abra_rhus = ['Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 'Tayum', 'Tineg', 'Tubo', 'Villaviciosa']
    data['Area'] = data['Area'].astype(str).str.strip()
    data = data[data['Area'].isin(abra_rhus)]

    # Transform to Long Format
    long = data.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # Strictly filter for only columns we tagged with a Sex breakdown (ignoring denominators)
    long = long[long['Metric'].str.contains('\|', na=False)]
    if long.empty:
        return pd.DataFrame()

    long[['Indicator', 'Sex']] = long['Metric'].str.split('|', expand=True)
    long['Count'] = pd.to_numeric(long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    final = long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Add standardized Period
    final['Period'] = get_period_label(filename)
    final['Source'] = filename
    return final

# 4. Sidebar Controller
with st.sidebar:
    st.header("⚙️ Data Entry")
    st.info("Upload your 2025 FHSIS CSV files here.")
    files = st.file_uploader("Drop Files", accept_multiple_files=True, type=['csv'])
    
    if st.button("🚀 Process & Build Dashboard", type="primary"):
        if files:
            all_data = []
            for f in files:
                res = process_fhsish_csv(f)
                if not res.empty:
                    all_data.append(res)
            
            if all_data:
                st.session_state.master_db = pd.concat(all_data, ignore_index=True)
                st.success("Successfully Normalized!")
            else:
                st.error("No accomplishment data found. Ensure these are service delivery CSVs.")

# 5. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra RHUs)")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Global Filter
    periods = sorted(db['Period'].unique())
    selected_period = st.select_slider("Select Reporting Period:", options=periods)
    
    # Filtered Data
    view_data = db[db['Period'] == selected_period]
    indicators = sorted(view_data['Indicator'].unique())
    
    # Generate 1 section per Indicator
    for ind in indicators:
        with st.container():
            st.divider()
            st.subheader(f"💉 {ind}")
            
            # Data for this vaccine
            ind_df = view_data[view_data['Indicator'] == ind].copy()
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("**Accomplishments by RHU**")
                # Bar chart with Male/Female split
                plot_data = ind_df.set_index('Area')[['Male', 'Female']]
                st.bar_chart(plot_data)
                
            with col2:
                st.write("**Leaderboard (Top 5)**")
                # Table
                top_5 = ind_df.sort_values(by='Total', ascending=False)[['Area', 'Total']].head(5)
                st.table(top_5)
                
                # Big Metric
                total_abra = int(ind_df['Total'].sum())
                st.metric("Total Count (Abra)", f"{total_abra:,}")

    # Export
    st.divider()
    csv = db.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Power BI Fact Table", csv, "Abra_Immunization_2025.csv", "text/csv")

else:
    st.warning("👈 Upload your FHSIS files in the sidebar to generate the automated indicators.")
