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

# 3. Enhanced Processing Logic (Handles XLSX and CSV)
def process_fhsish_file(file):
    filename = file.name
    try:
        if filename.lower().endswith('.xlsx'):
            # If it's an Excel file, we try to process the first visible sheet
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

    # Step 2: Extract Indicators (Row 5) and Sex Subheaders (Row 7)
    # Indicator names are in the Area row. Forward fill bridges across Male/Female cells.
    header_row = df.iloc[area_row_idx].ffill().astype(str).str.replace('\n', ' ').str.strip()
    
    # Sex sub-header row (Male/Female/Total) is 2 rows below Area in these templates
    sex_row_idx = area_row_idx + 2
    if sex_row_idx >= len(df): return pd.DataFrame()
    
    sex_row = df.iloc[sex_row_idx].fillna('').astype(str).str.strip().str.title()
    
    # Step 3: Combine Header + Sex and filter for Abra RHUs
    data = df.iloc[sex_row_idx + 1:].copy()
    data.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sex_row)]
    
    area_col_candidates = [c for c in data.columns if 'area' in str(c).lower()]
    if not area_col_candidates: return pd.DataFrame()
    data = data.rename(columns={area_col_candidates[0]: 'Area'})
    
    # Strict Abra Filter
    abra_rhus = [
        'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
        'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
        'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
        'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
        'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
    ]
    data['Area'] = data['Area'].astype(str).str.strip()
    data = data[data['Area'].isin(abra_rhus)]

    # Step 4: Normalize to Long Format (Star Schema style for Power BI)
    long = data.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # Filter: ONLY keep service metrics (Indicator + Sex). This ignores denominators.
    long = long[long['Metric'].str.contains('\|', na=False)]
    if long.empty: return pd.DataFrame()

    long[['Indicator', 'Sex']] = long['Metric'].str.split('|', expand=True)
    long['Count'] = pd.to_numeric(long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Step 5: Final Pivot to create clean Male/Female/Total columns
    final = long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Ensure standard columns exist
    for col in ['Male', 'Female', 'Total']:
        if col not in final.columns: final[col] = 0
            
    final['Period'] = get_period_label(filename)
    final['Source'] = filename
    return final

# 4. Sidebar Controller
with st.sidebar:
    st.header("📂 Data Entry")
    st.info("Upload your 2025 FHSIS CSV or XLSX files here.")
    # FIX: Added 'xlsx' to the allowed types
    files = st.file_uploader("Drop Files", accept_multiple_files=True, type=['csv', 'xlsx'])
    
    if st.button("🚀 Build Immunization Dashboard", type="primary"):
        if files:
            all_data = []
            for f in files:
                res = process_fhsish_file(f)
                if not res.empty: all_data.append(res)
            
            if all_data:
                st.session_state.master_db = pd.concat(all_data, ignore_index=True)
                st.success("Analysis Ready!")
            else:
                st.error("No valid accomplishment data found. Ensure these are the service delivery templates.")

# 5. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra RHUs)")

# Persistent Navigation
tab1, tab2 = st.tabs(["1 Immunization", "Upcoming Priorities"])

with tab1:
    if st.session_state.master_db is not None:
        db = st.session_state.master_db
        
        # Period Filter Sorter
        periods = sorted(db['Period'].unique())
        selected_period = st.select_slider("Select Reporting Month/Period:", options=periods)
        
        view_data = db[db['Period'] == selected_period]
        indicators = sorted(view_data['Indicator'].unique())
        
        # Generate 1 Visual Scorecard per Indicator (BCG, DPT, OPV, etc.)
        for ind in indicators:
            with st.container():
                st.divider()
                st.subheader(f"💉 {ind}")
                ind_df = view_data[view_data['Indicator'] == ind].copy()
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**RHU Performance Breakdown (Male vs Female)**")
                    # Display a stacked bar chart
                    plot_data = ind_df.set_index('Area')[['Male', 'Female']]
                    st.bar_chart(plot_data)
                with col2:
                    st.write("**Leaderboard**")
                    top_5 = ind_df.sort_values(by='Total', ascending=False)[['Area', 'Total']].head(5)
                    st.table(top_5)
                    total_abra = int(ind_df['Total'].sum())
                    st.metric(f"Total {ind} (Abra)", f"{total_abra:,}")

        # Final Master Export
        st.divider()
        st.subheader("📦 Master Database Export")
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Master CSV for Power BI", csv, "Abra_Imm_2025_Master.csv", "text/csv")
    else:
        st.warning("👈 Please upload your 2025 Immunization files (XLSX or CSV) in the sidebar to begin.")

with tab2:
    st.info("This section will be built once Immunization is perfected.")
