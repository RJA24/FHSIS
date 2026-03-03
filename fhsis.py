import streamlit as st
import pandas as pd
import re
import io

# 1. Page Configuration
st.set_page_config(page_title="Abra FHSIS App", layout="wide")

# 2. Persistent Session State
if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# 3. Intelligent Processing Engine
def process_file(uploaded_file):
    filename = uploaded_file.name
    is_excel = filename.lower().endswith('.xlsx')
    
    # --- STEP 1: Find the Header Row ---
    if is_excel:
        temp_df = pd.read_excel(uploaded_file, nrows=25, header=None)
    else:
        temp_df = pd.read_csv(uploaded_file, nrows=25, header=None)
    
    header_idx = -1
    for i, row in temp_df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            header_idx = i
            break
    
    if header_idx == -1:
        return pd.DataFrame() # Skip file if 'Area' not found

    uploaded_file.seek(0)
    if is_excel:
        df = pd.read_excel(uploaded_file, skiprows=header_idx)
    else:
        df = pd.read_csv(uploaded_file, skiprows=header_idx)
    
    # --- STEP 2: Handle Merged Excel Headers ---
    cols = pd.Series(df.columns).astype(str).str.replace('\n', ' ').str.strip()
    # Forward fill 'Unnamed' columns
    curr_main = ""
    for i in range(len(cols)):
        if not cols[i].startswith('Unnamed'):
            curr_main = cols[i]
        else:
            cols[i] = curr_main

    # Merge with sub-headers (Male, Female, Total) usually found in the first row of data
    sub_headers = df.iloc[0].fillna('').astype(str).str.strip().str.title()
    
    new_cols = []
    for i in range(len(cols)):
        sub = sub_headers[i]
        if sub in ['Male', 'Female', 'Total']:
            new_cols.append(f"{cols[i]}|{sub}")
        else:
            new_cols.append(cols[i])
            
    df.columns = new_cols
    df = df.drop(0).reset_index(drop=True)
    
    # --- STEP 3: Filter for Abra RHUs ---
    area_col = [c for c in df.columns if 'area' in c.lower()][0]
    df = df.rename(columns={area_col: 'Area'})
    df['Area'] = df['Area'].astype(str).str.strip()
    
    abra_rhus = [
        'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
        'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
        'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
        'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
        'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
    ]
    df = df[df['Area'].isin(abra_rhus)]
    
    # --- STEP 4: Melt and Pivot Accomplishments ---
    df_long = df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # Only keep metrics that have the Male/Female/Total breakdown
    df_long = df_long[df_long['Metric'].str.contains('\|', na=False)]
    if df_long.empty:
        return pd.DataFrame()

    df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
    df_long['Count'] = pd.to_numeric(df_long['Count'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Pivot to create separate Male, Female, and Total columns
    final_df = df_long.pivot_table(
        index=['Area', 'Indicator'], 
        columns='Sex', 
        values='Count', 
        aggfunc='sum'
    ).reset_index()
    
    # --- STEP 5: Add Intelligence (Metadata) ---
    final_df['Year'] = 2025 # Can be dynamic later
    
    # Extract Month/Period from filename
    fname_low = filename.lower()
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    final_df['Period'] = 'Annual'
    for m in months:
        if m in fname_low:
            final_df['Period'] = m.capitalize()
            break
            
    final_df['Source'] = filename
    return final_df

# 4. Sidebar: Data Control Portal
with st.sidebar:
    st.header("⚙️ Data Entry")
    st.info("Upload your RHU Accomplishment reports here.")
    uploaded_files = st.file_uploader("Upload CSV/Excel", accept_multiple_files=True, type=['csv', 'xlsx'])
    
    if st.button("🚀 Consolidate Data", type="primary"):
        if uploaded_files:
            all_data = []
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                res = process_file(f)
                if not res.empty:
                    all_data.append(res)
                progress.progress((i+1)/len(uploaded_files))
            
            if all_data:
                st.session_state.master_db = pd.concat(all_data, ignore_index=True)
                st.success("Successfully Processed!")
            else:
                st.error("Could not find accomplishment data in these files.")
        else:
            st.warning("Please select files first.")

# 5. Main Content: Priority Tabs
st.title("FHSIS Priority Health Outcomes - Abra")

tab1, tab2 = st.tabs(["1 Immunization", "Upcoming Priorities..."])

with tab1:
    if st.session_state.master_db is not None:
        db = st.session_state.master_db
        
        # --- Metrics Row ---
        m1, m2, m3 = st.columns(3)
        m1.metric("RHUs Covered", len(db['Area'].unique()))
        m2.metric("Total Accomplishments", int(db['Total'].sum()))
        m3.metric("Indicators Tracked", len(db['Indicator'].unique()))

        # --- Dashboard ---
        st.subheader("Monthly Breakdown")
        month_sel = st.selectbox("Select Month/Period:", sorted(db['Period'].unique()))
        indicator_sel = st.selectbox("Select Vaccine/Indicator:", sorted(db['Indicator'].unique()))
        
        chart_data = db[(db['Period'] == month_sel) & (db['Indicator'] == indicator_sel)]
        st.bar_chart(chart_data.set_index('Area')[['Male', 'Female']])
        
        # --- Data View ---
        st.subheader("Raw Consolidated Data")
        st.dataframe(db, use_container_width=True)
        
        # Download
        csv = db.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Master CSV for Power BI", csv, "Abra_Immunization_FactTable.csv", "text/csv")
    else:
        st.warning("👈 Please upload the 2025 immunization files in the sidebar to view the dashboard.")
