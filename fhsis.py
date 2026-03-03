import streamlit as st
import pandas as pd
import re
import io

# 1. Page Configuration
st.set_page_config(page_title="Abra FHSIS App", layout="wide")

if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Intelligent Processing Engine (Multi-Sheet Aware)
def process_rhu_workbook(uploaded_file):
    filename = uploaded_file.name
    is_excel = filename.lower().endswith('.xlsx')
    
    if not is_excel:
        st.error(f"{filename} is not an Excel file. Please upload .xlsx files for multi-sheet processing.")
        return pd.DataFrame()

    all_months_data = []
    
    # Load the entire workbook
    xls = pd.ExcelFile(uploaded_file)
    
    # Filter for month sheets only (January to December)
    target_months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", 
                     "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    
    available_month_sheets = [s for s in xls.sheet_names if s.upper() in target_months]
    
    if not available_month_sheets:
        st.warning(f"No monthly sheets found in {filename}. Checking if it's a single-period report...")
        available_month_sheets = xls.sheet_names[:1] # Fallback to first sheet

    for sheet_name in available_month_sheets:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        # Step 1: Find the 'Area' row dynamically
        header_idx = -1
        for i, row in df.iterrows():
            if any(str(v).strip().lower() == 'area' for v in row.values):
                header_idx = i
                break
        
        if header_idx == -1: continue

        # Step 2: Handle Headers (Indicator + Sex)
        # Indicator row
        header_row = df.iloc[header_idx].fillna(method='ffill').astype(str).str.strip()
        # Sub-header row (Male/Female/Total) is usually 2 rows below Area
        sub_header_row = df.iloc[header_idx + 2].fillna('').astype(str).str.strip().str.title()
        
        # Define Data
        data_df = df.iloc[header_idx + 3:].copy()
        data_df.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sub_header_row)]
        
        # Step 3: Filter for Abra RHUs
        area_col = [c for c in data_df.columns if 'area' in c.lower()]
        if not area_col: continue
        data_df = data_df.rename(columns={area_col[0]: 'Area'})
        
        abra_rhus = [
            'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
            'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
            'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
            'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
            'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
        ]
        data_df['Area'] = data_df['Area'].astype(str).str.strip()
        data_df = data_df[data_df['Area'].isin(abra_rhus)]

        # Step 4: Melt and Pivot
        df_long = data_df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
        df_long = df_long[df_long['Metric'].str.contains('\|', na=False)]
        
        if df_long.empty: continue

        df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
        df_long['Count'] = pd.to_numeric(df_long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # Final monthly table
        final = df_long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
        
        # Metadata
        final['Month'] = sheet_name.capitalize()
        final['Year'] = 2025 # Default
        final['Source'] = filename
        
        all_months_data.append(final)

    if all_months_data:
        return pd.concat(all_months_data, ignore_index=True)
    return pd.DataFrame()

# 3. Sidebar UI
with st.sidebar:
    st.title("Data Entry")
    st.info("Upload the RHU Immunization Excel workbooks containing monthly sheets.")
    files = st.file_uploader("Upload .xlsx files", accept_multiple_files=True, type=['xlsx'])
    
    if st.button("🚀 Load All Months", type="primary"):
        if files:
            results = []
            for f in files:
                processed = process_rhu_workbook(f)
                if not processed.empty: results.append(processed)
            
            if results:
                st.session_state.master_db = pd.concat(results, ignore_index=True)
                st.success(f"Success! Loaded {len(st.session_state.master_db)} records.")
            else:
                st.error("Could not find monthly accomplishment data in those workbooks.")

# 4. Main Dashboard
st.title("FHSIS Priority 1: Immunization (Abra)")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    tab_data, tab_viz = st.tabs(["📋 Consolidated Fact Table", "📊 RHU Metrics"])
    
    with tab_data:
        st.subheader("Monthly Performance Database")
        st.dataframe(db, use_container_width=True)
        
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Fact Table (CSV)", csv, "Abra_Imm_Monthly_Master.csv", "text/csv")
        
    with tab_viz:
        col1, col2 = st.columns(2)
        with col1:
            month_sel = st.selectbox("Filter Month:", sorted(db['Month'].unique()))
        with col2:
            ind_sel = st.selectbox("Filter Indicator:", sorted(db['Indicator'].unique()))
        
        # Plot
        viz_data = db[(db['Month'] == month_sel) & (db['Indicator'] == ind_sel)].groupby('Area')[['Male', 'Female']].sum()
        st.bar_chart(viz_data)
else:
    st.info("👈 Use the sidebar to upload the Excel files. I will automatically scan through the January to December sheets for you.")
