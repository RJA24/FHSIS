import streamlit as st
import pandas as pd
import re

# 1. Page Setup
st.set_page_config(page_title="Abra FHSIS App", layout="wide")

if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 2. Intelligent Processing Logic
def process_rhu_file(uploaded_file):
    filename = uploaded_file.name
    is_excel = filename.lower().endswith('.xlsx')
    
    # Load data
    if is_excel:
        df = pd.read_excel(uploaded_file, header=None)
    else:
        df = pd.read_csv(uploaded_file, header=None)

    # Step 1: Find the 'Area' row
    header_idx = -1
    for i, row in df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            header_idx = i
            break
    
    if header_idx == -1: return pd.DataFrame()

    # Step 2: Extract Headers (Row with Indicators) and Subheaders (Male/Female/Total)
    header_row = df.iloc[header_idx].fillna(method='ffill').astype(str).str.strip()
    # The sub-header (Male/Female) is usually 1 or 2 rows below 'Area'
    sub_header_row = df.iloc[header_idx + 2].fillna('').astype(str).str.strip().str.title()
    
    # Data starts after headers
    data_df = df.iloc[header_idx + 3:].copy()
    data_df.columns = [f"{h}|{s}" if s in ['Male', 'Female', 'Total'] else h for h, s in zip(header_row, sub_header_row)]
    
    # Step 3: Filter for Abra RHUs
    area_col = [c for c in data_df.columns if 'area' in c.lower()][0]
    data_df = data_df.rename(columns={area_col: 'Area'})
    
    abra_rhus = [
        'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
        'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
        'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
        'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
        'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
    ]
    data_df['Area'] = data_df['Area'].astype(str).str.strip()
    data_df = data_df[data_df['Area'].isin(abra_rhus)]

    # Step 4: Transform to Long Format
    df_long = data_df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # Filter for only accomplishment columns (those we tagged with '|')
    df_long = df_long[df_long['Metric'].str.contains('\|', na=False)]
    if df_long.empty: return pd.DataFrame()

    df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
    df_long['Count'] = pd.to_numeric(df_long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # Step 5: Final Pivot to get Male/Female/Total columns
    final = df_long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Metadata
    final['Year'] = 2025
    fname = filename.lower()
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    final['Period'] = next((m.capitalize() for m in months if m in fname), 'Annual')
    final['Source'] = filename

    return final

# 3. Sidebar UI
with st.sidebar:
    st.title("Data Entry")
    files = st.file_uploader("Upload Immunization Reports", accept_multiple_files=True, type=['csv', 'xlsx'])
    if st.button("🚀 Consolidate Now", type="primary"):
        if files:
            results = []
            for f in files:
                processed = process_rhu_file(f)
                if not processed.empty: results.append(processed)
            
            if results:
                st.session_state.master_db = pd.concat(results, ignore_index=True)
                st.success("Data loaded!")
            else:
                st.error("No valid data found in those files.")

# 4. Main Dashboard
st.title("FHSIS Priority 1: Immunization")

if st.session_state.master_db is not None:
    db = st.session_state.master_db
    
    # Tab layout
    tab_data, tab_viz = st.tabs(["📋 Consolidated Table", "📊 RHU Visuals"])
    
    with tab_data:
        st.subheader("Master Accomplishment List")
        st.dataframe(db, use_container_width=True)
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Master CSV for Power BI", csv, "Abra_Immunization_Master.csv", "text/csv")
        
    with tab_viz:
        st.subheader("RHU Performance Comparison")
        ind_list = sorted(db['Indicator'].unique())
        selected_ind = st.selectbox("Select Indicator:", ind_list)
        
        # Plot
        viz_data = db[db['Indicator'] == selected_ind].groupby('Area')[['Male', 'Female']].sum()
        st.bar_chart(viz_data)
else:
    st.info("Waiting for data. Please upload files in the sidebar to generate the immunization dashboard.")
