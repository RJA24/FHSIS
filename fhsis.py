import streamlit as st
import pandas as pd

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
    name = filename.lower()
    if "cpab" in name or "bcg" in name: return "Immunization - BCG/HepB"
    if "dpt" in name or "hib" in name: return "Immunization - DPT/HiB/HepB"
    if "opv" in name or "ipv" in name: return "Immunization - Polio"
    if "pcv" in name: return "Immunization - PCV"
    if "mmr" in name or "fic" in name: return "Immunization - MMR/FIC"
    if "hpv" in name: return "Immunization - HPV"
    if "diarrhea" in name: return "Sick Children - Diarrhea"
    if "pneumonia" in name: return "Sick Children - Pneumonia"
    if "mam" in name or "sam" in name: return "Nutrition - Malnutrition"
    if "vitamin a" in name: return "Nutrition - Vitamin A"
    if "mnp" in name: return "Nutrition - MNP"
    if "lns" in name: return "Nutrition - LNS-SQ"
    if "low birth" in name or "bf" in name: return "Nutrition - LBW/BF"
    return "Uncategorized Indicator"

@st.cache_data
def parse_fhsis_template(uploaded_file):
    # 1. Handle both CSV and Excel securely with encoding fallbacks
    file_name = uploaded_file.name.lower()
    
    try:
        if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            try:
                df = pd.read_csv(uploaded_file, header=None, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=None, encoding='latin-1')
    except Exception as e:
        return None, f"Could not read file: {e}"

    # Clean up string columns
    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)

    # 2. Locate Area Column
    area_col_index = None
    for col in df.columns:
        if df[col].astype(str).isin(['Bangued', 'Manabo']).any():
            area_col_index = col
            break
            
    if area_col_index is None:
        return None, "Could not locate Area column."

    # 3. Locate Data Bounds
    car_start = df[df[area_col_index] == 'C A R'].index.min()
    abra_start = df[df[area_col_index] == 'Abra'].index.min()
    apayao_start = df[df[area_col_index] == 'Apayao'].index.min()

    if pd.isna(car_start): car_start = abra_start - 3
    if pd.isna(abra_start): abra_start = 0
    if pd.isna(apayao_start): apayao_start = len(df)

    # 4. --- THE HEADER FLATTENER ---
    header_rows = df.iloc[max(0, car_start-3):car_start].copy()
    header_rows = header_rows.replace(['nan', 'None', '', 'NaN'], pd.NA)
    header_rows = header_rows.ffill(axis=1)

    flat_headers = []
    for col in df.columns:
        col_texts = [str(val) for val in header_rows[col].values if pd.notna(val)]
        
        clean_texts = []
        for text in col_texts:
            if text not in clean_texts and "Unnamed" not in text:
                clean_texts.append(text)
        
        header_name = " | ".join(clean_texts)
        if not header_name:
            header_name = f"Col_{col}"
        flat_headers.append(header_name)
        
    df.columns = flat_headers

    # 5. Slice the Abra Block
    abra_df = df.iloc[abra_start:apayao_start].copy()
    area_col_name = df.columns[area_col_index]
    clean_df = abra_df[abra_df[area_col_name].isin(ABRA_MUNIS)].copy()
    
    # Clean up the grid
    clean_df.rename(columns={area_col_name: 'Municipality'}, inplace=True)
    clean_df.dropna(axis=1, how='all', inplace=True)
    
    # Filter to only keep Municipality, Total, and % columns to clean up the UI
    final_cols = ['Municipality'] + [col for col in clean_df.columns if 'Total' in col or '%' in col]
    
    if len(final_cols) == 1:
        final_cols = clean_df.columns.tolist()

    return clean_df[final_cols], "Success"

# ---------------------------------------------------------
# APP UI & ROUTING
# ---------------------------------------------------------
st.title("🏥 Abra Provincial FHSIS Dashboard")
st.markdown("### Automated Data Pipeline (2021-2025)")

with st.expander("📂 Upload FHSIS Templates", expanded=True):
    uploaded_files = st.file_uploader(
        "Drag and drop FHSIS CSV or Excel files here", 
        type=['csv', 'xlsx'], 
        accept_multiple_files=True
    )

if uploaded_files:
    st.success(f"{len(uploaded_files)} files loaded successfully.")
    
    # Group files by Indicator Type
    grouped_files = {}
    for file in uploaded_files:
        indicator = detect_indicator_type(file.name)
        if indicator not in grouped_files:
            grouped_files[indicator] = []
        grouped_files[indicator].append(file)
        
    tabs = st.tabs(list(grouped_files.keys()))
    
    for i, (indicator, files) in enumerate(grouped_files.items()):
        with tabs[i]:
            st.markdown(f"### {indicator} Data")
            
            for file in files:
                parsed_data, status = parse_fhsis_template(file)
                
                if parsed_data is not None:
                    with st.expander(f"📄 {file.name}", expanded=False):
                        st.dataframe(parsed_data, use_container_width=True)
                else:
                    st.error(f"Failed to load {file.name}: {status}")
else:
    st.info("Awaiting file upload... Drop your monthly CSVs above.")
