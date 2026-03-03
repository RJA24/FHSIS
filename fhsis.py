import streamlit as st
import pandas as pd
import re
import io

# 1. Page Configuration
st.set_page_config(page_title="Abra FHSIS App", layout="wide")

if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Extract Period/Month from String
def extract_period(text):
    text = text.upper()
    months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", 
              "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
              "JAN", "FEB", "MAR", "APR", "JUN", "JUL", "AUG", "SEPT", "OCT", "NOV", "DEC"]
    
    for m in months:
        if m in text:
            # Standardize short names to full names for better sorting
            full_months = {"JAN": "January", "FEB": "February", "MAR": "March", "APR": "April", "JUN": "June", 
                           "JUL": "July", "AUG": "August", "SEPT": "September", "OCT": "October", "NOV": "November", "DEC": "December"}
            return full_months.get(m, m.capitalize())
            
    if "Q1" in text: return "1st Quarter"
    if "Q2" in text: return "2nd Quarter"
    if "Q3" in text: return "3rd Quarter"
    if "Q4" in text: return "4th Quarter"
    if "ELIG" in text or "POP" in text: return "Eligible Population"
    if "2025" in text or "ANNUAL" in text: return "Annual"
    
    return "Unknown Period"

# 3. Core Processing Logic
def process_data(file):
    filename = file.name
    is_excel = filename.lower().endswith('.xlsx')
    results = []

    if is_excel:
        xls = pd.ExcelFile(file)
        # Look for monthly sheets or process the active one
        target_months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", 
                         "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
        sheets = [s for s in xls.sheet_names if s.upper() in target_months]
        if not sheets: sheets = xls.sheet_names[:1] 
        
        for sn in sheets:
            df_raw = pd.read_excel(xls, sheet_name=sn, header=None)
            processed = clean_rhu_table(df_raw, sn, filename)
            if not processed.empty: results.append(processed)
    else:
        # It's a CSV
        df_raw = pd.read_csv(file, header=None)
        processed = clean_rhu_table(df_raw, filename, filename)
        if not processed.empty: results.append(processed)
        
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

def clean_rhu_table(df, period_text, filename):
    # Step 1: Find 'Area'
    header_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            header_idx = i
            break
    if header_idx == -1: return pd.DataFrame()

    # Step 2: Extract Indicators and Sex
    # Forward fill headers to fix merged cells
    header_row = df.iloc[header_idx].fillna(method='ffill').astype(str).str.strip()
    sub_header_row = df.iloc[header_idx + 2].fillna('').astype(str).str.strip().str.title()
    
    data_df = df.iloc[header_idx + 3:].copy()
    data_df.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sub_header_row)]
    
    # Step 3: Filter Abra
    area_col = [c for c in data_df.columns if 'area' in c.lower()]
    if not area_col: return pd.DataFrame()
    data_df = data_df.rename(columns={area_col[0]: 'Area'})
    
    abra_rhus = ['Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 'Tayum', 'Tineg', 'Tubo', 'Villaviciosa']
    data_df['Area'] = data_df['Area'].astype(str).str.strip()
    data_df = data_df[data_df['Area'].isin(abra_rhus)]

    # Step 4: Melt and Pivot
    df_long = data_df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    df_long = df_long[df_long['Metric'].str.contains('\|', na=False)]
    if df_long.empty: return pd.DataFrame()

    df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
    df_long['Count'] = pd.to_numeric(df_long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    final = df_long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Metadata - CRITICAL FIX: Ensure 'Month' column exists
    final['Month'] = extract_period(period_text)
    final['Year'] = 2025
    final['Source'] = filename
    return final

# 4. UI logic
with st.sidebar:
    st.title("Data Entry")
    files = st.file_uploader("Upload Immunization CSVs or Excel", accept_multiple_files=True, type=['csv', 'xlsx'])
    if st.button("🚀 Load & Consolidate", type="primary"):
        if files:
            all_results = []
            for f in files:
                try:
                    res = process_data(f)
                    if not res.empty: all_results.append(res)
                except Exception as e:
                    st.error(f"Error in {f.name}: {e}")
            
            if all_results:
                st.session_state.master_db = pd.concat(all_results, ignore_index=True)
                st.success("Database Updated!")

# 5. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra)")



if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Always ensure columns for visuals
    for col in ['Male', 'Female', 'Total']:
        if col not in db.columns: db[col] = 0

    tab_data, tab_viz = st.tabs(["📋 Consolidated Fact Table", "📊 RHU Metrics"])
    
    with tab_data:
        st.dataframe(db, use_container_width=True)
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Fact Table (CSV)", csv, "Abra_Imm_Master.csv", "text/csv")
        
    with tab_viz:
        col1, col2 = st.columns(2)
        with col1:
            month_list = sorted(db['Month'].unique())
            month_sel = st.selectbox("Filter Period:", month_list)
        with col2:
            ind_list = sorted(db['Indicator'].unique())
            ind_sel = st.selectbox("Filter Indicator:", ind_list)
        
        viz_data = db[(db['Month'] == month_sel) & (db['Indicator'] == ind_sel)].groupby('Area')[['Male', 'Female']].sum()
        st.bar_chart(viz_data)
else:
    st.info("👈 Upload your files in the sidebar. I can now handle the specific CSV formats you sent!")
