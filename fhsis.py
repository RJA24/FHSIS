import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
st.set_page_config(page_title="Abra FHSIS Dashboard", layout="wide", page_icon="🏥")

ABRA_MUNIS = [
    'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 
    'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 
    'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 
    'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 
    'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
]

# ---------------------------------------------------------
# THE INTELLIGENT PARSER
# ---------------------------------------------------------
def detect_indicator_type(filename):
    """Sniffs the filename to determine the FHSIS indicator category."""
    name = filename.lower()
    if "cpab" in name or "bcg" in name: return "Immunization - BCG/HepB"
    if "dpt" in name or "hib" in name: return "Immunization - DPT/HiB/HepB"
    if "opv" in name or "ipv" in name: return "Immunization - Polio"
    if "pcv" in name: return "Immunization - PCV"
    if "mmr" in name or "fic" in name: return "Immunization - MMR/FIC"
    if "diarrhea" in name: return "Sick Children - Diarrhea"
    if "pneumonia" in name: return "Sick Children - Pneumonia"
    if "mam" in name or "sam" in name: return "Nutrition - Malnutrition"
    return "Uncategorized Indicator"

@st.cache_data
def parse_fhsis_template(uploaded_file):
    # Read raw file
    df = pd.read_csv(uploaded_file, header=None)
    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)

    # 1. Locate the Area Column
    area_col_index = None
    for col in df.columns:
        if df[col].astype(str).isin(['Bangued', 'Manabo']).any():
            area_col_index = col
            break
            
    if area_col_index is None:
        return None, "Could not locate Area column."

    # 2. Slice the Abra Block
    abra_start = df[df[area_col_index] == 'Abra'].index.min()
    apayao_start = df[df[area_col_index] == 'Apayao'].index.min()

    if pd.isna(abra_start): abra_start = 0
    if pd.isna(apayao_start): apayao_start = len(df)

    abra_df = df.iloc[abra_start:apayao_start].copy()
    
    # 3. Filter precisely for 27 Municipalities (Ignore RHU/Hospital splits for now)
    clean_df = abra_df[abra_df[area_col_index].isin(ABRA_MUNIS)].copy()
    
    # Clean up the grid
    clean_df.rename(columns={area_col_index: 'Municipality'}, inplace=True)
    clean_df.dropna(axis=1, how='all', inplace=True)
    
    return clean_df, "Success"

# ---------------------------------------------------------
# APP UI & ROUTING
# ---------------------------------------------------------
st.title("🏥 Abra Provincial FHSIS Dashboard")
st.markdown("### Automated Data Pipeline (2021-2025)")

with st.expander("📂 Upload FHSIS Templates", expanded=True):
    uploaded_files = st.file_uploader(
        "Drag and drop FHSIS CSV files here", 
        type=['csv', 'xlsx'], 
        accept_multiple_files=True
    )

if uploaded_files:
    st.success(f"{len(uploaded_files)} files loaded successfully.")
    
    # Group files by Indicator Type to organize the Dashboard
    grouped_files = {}
    for file in uploaded_files:
        indicator = detect_indicator_type(file.name)
        if indicator not in grouped_files:
            grouped_files[indicator] = []
        grouped_files[indicator].append(file)
        
    # Create Tabs for each Indicator Category
    tabs = st.tabs(list(grouped_files.keys()))
    
    for i, (indicator, files) in enumerate(grouped_files.items()):
        with tabs[i]:
            st.markdown(f"### {indicator} Data")
            
            for file in files:
                parsed_data, status = parse_fhsis_template(file)
                
                if parsed_data is not None:
                    with st.expander(f"📄 {file.name}", expanded=False):
                        st.dataframe(parsed_data, use_container_width=True)
                        
                        # Data Validation Check
                        missing = set(ABRA_MUNIS) - set(parsed_data['Municipality'].tolist())
                        if missing:
                            st.warning(f"Missing Data for: {', '.join(missing)}")
                        else:
                            st.success("All 27 Municipalities extracted successfully.")
else:
    st.info("Awaiting file upload... Drop your monthly CSVs above.")
