import streamlit as st
import pandas as pd
import re

# Set page config
st.set_page_config(page_title="Abra FHSIS Processor", layout="wide")

# Initialize session state to persist data
if 'master_db' not in st.session_state:
    st.session_state.master_db = None

# --- SIDEBAR: DATA CONTROL ---
with st.sidebar:
    st.header("Data Control")
    uploaded_files = st.file_uploader("Upload Immunization Files", accept_multiple_files=True, type=['csv', 'xlsx'])
    
    if st.button("Consolidate Immunization", type="primary"):
        if uploaded_files:
            all_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Processing {file.name}...")
                try:
                    df = process_file(file)
                    if not df.empty: all_data.append(df)
                except Exception as e:
                    st.error(f"Error in {file.name}: {e}")
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            if all_data:
                st.session_state.master_db = pd.concat(all_data, ignore_index=True)
                st.success("Processing complete!")
                status_text.text("Ready.")
            else:
                st.warning("No valid accomplishment data found.")
        else:
            st.warning("Please upload files first.")

# --- MAIN PAGE: DASHBOARD ---
st.title("FHSIS Immunization Dashboard - Abra")

tab1, tab2 = st.tabs(["1 Immunization", "Upcoming Priorities"])

with tab1:
    if st.session_state.master_db is not None:
        st.write(f"Normalized records: **{len(st.session_state.master_db)}**")
        
        # Download Button
        csv = st.session_state.master_db.to_csv(index=False).encode('utf-8')
        st.download_button("Download Master CSV", csv, "Abra_Immunization_2025.csv", "text/csv")
        
        # Visuals
        indicators = sorted(st.session_state.master_db['Indicator'].unique())
        sel_ind = st.selectbox("Select Indicator:", indicators)
        
        chart_data = st.session_state.master_db[st.session_state.master_db['Indicator'] == sel_ind]
        st.bar_chart(chart_data.groupby('Area')[['Male', 'Female', 'Total']].sum())
        
        st.dataframe(st.session_state.master_db)
    else:
        st.info("Upload your CSV/Excel immunization files in the sidebar to begin.")

# --- PROCESSING LOGIC ---
def process_file(uploaded_file):
    filename = uploaded_file.name
    is_excel = filename.lower().endswith('.xlsx')
    
    # 1. Read to find the header
    if is_excel: temp_df = pd.read_excel(uploaded_file, nrows=20, header=None)
    else: temp_df = pd.read_csv(uploaded_file, nrows=20, header=None)
    
    header_idx = 0
    for i, row in temp_df.iterrows():
        if any(str(v).strip().lower() == 'area' for v in row.values):
            header_idx = i
            break
            
    uploaded_file.seek(0)
    if is_excel: df = pd.read_excel(uploaded_file, skiprows=header_idx)
    else: df = pd.read_csv(uploaded_file, skiprows=header_idx)
    
    # 2. Clean and Flatten headers
    cols = pd.Series(df.columns).astype(str).str.replace('\n', ' ').str.strip()
    sub_headers = df.iloc[0].fillna('').astype(str).str.strip().str.title()
    
    new_cols = []
    curr_main = ""
    for i in range(len(cols)):
        if not cols[i].startswith('Unnamed'): curr_main = cols[i]
        sub = sub_headers[i]
        if sub in ['Male', 'Female', 'Total']:
            new_cols.append(f"{curr_main}|{sub}")
        else:
            new_cols.append(cols[i])
    df.columns = new_cols
    df = df.drop(0).reset_index(drop=True)
    
    # 3. Filter Abra
    area_col = [c for c in df.columns if 'area' in c.lower()][0]
    df = df.rename(columns={area_col: 'Area'})
    abra_rhus = ['Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 'Tayum', 'Tineg', 'Tubo', 'Villaviciosa']
    df = df[df['Area'].astype(str).str.strip().isin(abra_rhus)]
    
    # 4. Melt and Pivot
    df_long = df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    df_long = df_long[df_long['Metric'].str.contains('\|')]
    df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
    df_long['Count'] = pd.to_numeric(df_long['Count'], errors='coerce').fillna(0)
    
    final_df = df_long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    final_df['Year'] = 2025
    return final_df
