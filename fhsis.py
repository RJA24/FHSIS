import streamlit as st
import pandas as pd
import re

# Set up the page layout
st.set_page_config(page_title="Abra FHSIS Processor", layout="wide")
st.title("Immunization Data Normalizer (Abra RHUs Only)")

# Create the Tabs
tab1, tab2 = st.tabs(["1 Immunization", "Upcoming Priorities"])

def get_immunization_category(filename):
    fname = filename.upper()
    if 'CPAB' in fname or 'BCG' in fname or 'HEPA' in fname or 'HEPB' in fname: return 'CPAB, BCG, HepB'
    if 'DPT' in fname or 'HIB' in fname: return 'DPT-HiB-HepB'
    if 'OPV' in fname or 'IPV' in fname: return 'OPV and IPV'
    if 'PCV' in fname: return 'PCV'
    if 'MMR' in fname or 'FIC' in fname or 'CIC' in fname: return 'MMR, FIC, CIC'
    return 'Other Immunization'

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
    # Fill unnamed columns
    cols = pd.Series(df.columns)
    current_main = ""
    for i in range(len(cols)):
        if not str(cols[i]).startswith('Unnamed'): current_main = str(cols[i]).strip()
        else: cols[i] = current_main
    
    # Merge with sub-headers (Male, Female, Total)
    sub_headers = df.iloc[0].fillna('').astype(str).str.strip()
    new_cols = []
    for i in range(len(cols)):
        sub = sub_headers[i]
        if sub in ['Male', 'Female', 'Total']:
            new_cols.append(f"{cols[i]}|{sub}")
        else:
            new_cols.append(cols[i])
    df.columns = new_cols
    df = df.drop(0).reset_index(drop=True)
    
    # 3. Filter for Abra
    area_col = [c for c in df.columns if 'area' in c.lower()][0]
    df = df.rename(columns={area_col: 'Area'})
    abra_rhus = ['Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 'Tayum', 'Tineg', 'Tubo', 'Villaviciosa']
    df = df[df['Area'].astype(str).str.strip().isin(abra_rhus)]
    
    # 4. Melt and Pivot
    df_long = df.melt(id_vars=['Area'], var_name='Metric', value_name='Count')
    
    # DEFENSIVE FILTER: Only rows with '|' (Accomplishments)
    df_long = df_long[df_long['Metric'].str.contains('\|', na=False)]
    
    # If no data found, return empty
    if df_long.empty: return pd.DataFrame()
    
    df_long[['Indicator', 'Sex']] = df_long['Metric'].str.split('|', expand=True)
    df_long['Count'] = pd.to_numeric(df_long['Count'], errors='coerce').fillna(0)
    
    final_df = df_long.pivot_table(index=['Area', 'Indicator'], columns='Sex', values='Count', aggfunc='sum').reset_index()
    
    # Add metadata
    final_df['Program'] = get_immunization_category(filename)
    final_df['Period'] = 'Monthly' if any(m in filename for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']) else 'Quarterly/Annual'
    final_df['Year'] = 2025
    return final_df

# UI
with tab1:
    uploaded_files = st.file_uploader("Upload Immunization files", accept_multiple_files=True, type=['csv', 'xlsx'])
    if uploaded_files and st.button("Consolidate Immunization"):
        data_list = []
        for file in uploaded_files:
            try:
                res = process_file(file)
                if not res.empty: data_list.append(res)
            except Exception as e:
                st.error(f"Error in {file.name}: {e}")
        
        if data_list:
            master = pd.concat(data_list)
            st.dataframe(master)
            csv = master.to_csv(index=False).encode('utf-8')
            st.download_button("Download Master CSV", csv, "Abra_Immunization_2025.csv", "text/csv")
