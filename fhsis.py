import streamlit as st
import pandas as pd
import re

# 1. Page Config
st.set_page_config(page_title="Abra FHSIS Command Center", layout="wide")

# Initialize Session State
if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Resilient Chronological Period Mapping
def get_period_label(text):
    text = str(text).upper()
    # Using numeric prefixes ensures the slider sorts Jan -> Dec, not alphabetically
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
    try:
        df = pd.read_csv(file, header=None)
    except:
        return pd.DataFrame()
    
    # Step 1: Find the row where data begins (The "Area" row)
    area_row_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            area_row_idx = i
            break
    
    if area_row_idx == -1:
        return pd.DataFrame()

    # Step 2: Identify Indicators and Sex Breakdowns
    # Forward fill headers to bridge across merged Male/Female cells
    header_row = df.iloc[area_row_idx].fillna(method='ffill').astype(str).str.strip()
    
    # Scan for the sub-header row (Male/Female/Total)
    # It is usually 1-3 rows below the main Area header
    sex_row_idx = -1
    for offset in range(1, 5):
        row_vals = df.iloc[area_row_idx + offset].fillna('').astype(str).str.strip().str.title()
        if any(v in ['Male', 'Female', 'Total'] for v in row_vals):
            sex_row_idx = area_row_idx + offset
            sex_row = row_vals
            break
    
    if sex_row_idx == -1:
        return pd.DataFrame() # Skip file if no Male/Female columns found

    # Step 3: Combine Header + Sex and filter for Abra RHUs
    data = df.iloc[sex_row_idx + 1:].copy()
    data.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sex_row)]
    
    # Rename the Area column reliably
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

    # Step 4: Normalize to Long Format (Star Schema Style)
    long = data.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # CRITICAL: Ignore population denominators. Only keep metrics with '|' (Indicator + Sex)
    long = long[long['Metric'].str.contains('\|', na=False)]
    if long.empty:
        return pd.DataFrame()

    long[['Indicator', 'Sex']] = long['Metric'].str.split('|', expand=True)
    long['Count'] = pd.to_numeric(long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Step 5: Pivot so Male, Female, and Total are distinct columns
    final = long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Standardize columns (ensures 'Total' exists even if empty)
    for col in ['Male', 'Female', 'Total']:
        if col not in final.columns:
            final[col] = 0
            
    final['Period'] = get_period_label(filename)
    final['Source'] = filename
    return final

# 4. Sidebar Controller
with st.sidebar:
    st.header("📂 Data Controller")
    st.info("Upload the FHSIS CSV files for Abra RHUs.")
    files = st.file_uploader("Drop 2025 CSVs here", accept_multiple_files=True, type=['csv'])
    
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
                st.error("Could not find accomplishment data. Ensure these are service delivery CSVs.")

# 5. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra RHU Level)")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Safe check for 'Period' column to avoid KeyError
    if 'Period' in db.columns:
        periods = sorted(db['Period'].unique())
        selected_period = st.select_slider("Select Reporting Period:", options=periods)
        
        # Filter data for selected period
        view_data = db[db['Period'] == selected_period]
        indicators = sorted(view_data['Indicator'].unique())
        
        # Generate 1 Visual Scorecard per Indicator
        for ind in indicators:
            with st.container():
                st.divider()
                st.subheader(f"💉 {ind}")
                
                ind_df = view_data[view_data['Indicator'] == ind].copy()
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Performance by RHU (Male vs Female)**")
                    # Stacked Bar Chart for Male/Female split
                    plot_data = ind_df.set_index('Area')[['Male', 'Female']]
                    st.bar_chart(plot_data)
                
                with col2:
                    st.write("**Leaderboard**")
                    # Top Performing RHUs
                    top_5 = ind_df.sort_values(by='Total', ascending=False)[['Area', 'Total']].head(5)
                    st.table(top_5)
                    
                    # High-level Metric
                    total_abra = int(ind_df['Total'].sum())
                    st.metric(f"Total {ind} (Abra)", f"{total_abra:,}")

        # Final Master Export
        st.divider()
        st.subheader("📦 Master Database Export")
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Power BI Fact Table", csv, "Abra_Immunization_2025_FactTable.csv", "text/csv")
    else:
        st.error("Error: 'Period' column missing from processed data. Please check file formatting.")

else:
    st.warning("👈 Please upload your 2025 Immunization CSVs in the sidebar to generate the indicators.")
