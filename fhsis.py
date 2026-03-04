import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FHSIS Immunization Dashboard", page_icon="💉", layout="wide")

# --- DATA CLEANING FUNCTION ---
@st.cache_data
def load_and_clean_fhsis_data(uploaded_file):
    """
    Cleans the multi-header FHSIS Excel/CSV files into a flat pandas DataFrame.
    """
    try:
        # Read file, skipping the first 4 rows of metadata
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=4, header=[0, 1])
        else:
            df = pd.read_excel(uploaded_file, skiprows=4, header=[0, 1])

        # Fix "Merged Cells" issue by forward-filling the top header
        level_0 = pd.Series(df.columns.get_level_values(0)).replace(r'^Unnamed:.*', np.nan, regex=True).ffill()
        level_1 = pd.Series(df.columns.get_level_values(1)).replace(r'^Unnamed:.*', '', regex=True)
        
        # Combine the top and bottom headers
        flat_cols = []
        for top, bottom in zip(level_0, level_1):
            top_str = str(top).strip().replace('\n', ' ')
            bottom_str = str(bottom).strip().replace('\n', ' ')
            if bottom_str and bottom_str not in top_str:
                flat_cols.append(f"{top_str}_{bottom_str}")
            else:
                flat_cols.append(top_str)
                
        df.columns = flat_cols

        # Standardize the Area column
        df.rename(columns={df.columns[0]: 'Area'}, inplace=True)
        
        # Clean up rows: Drop rows where 'Area' is empty or just says 'Area'
        df.dropna(subset=['Area'], inplace=True)
        df = df[~df['Area'].str.contains('Area', na=False, case=False)]
        
        # Convert data columns to numeric, replacing errors with 0
        for col in df.columns:
            if col not in ['Area', 'Interpretation', 'Recommendation/Actions Taken']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df.reset_index(drop=True, inplace=True)
        return df

    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("FHSIS App")
    page = st.radio("Navigation", ["📊 Dashboard", "📁 Data Uploader"])
    
    st.markdown("---")
    
    if page == "📊 Dashboard":
        st.subheader("Global Filters")
        gender_filter = st.selectbox(
            "Select Demographic",
            options=["Total", "Male", "Female"],
            help="This selection applies to all indicators in the dashboard."
        )

# --- SESSION STATE TO STORE UPLOADED DATA ---
if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = {}

# --- MAIN DASHBOARD PAGE ---
if page == "📊 Dashboard":
    st.title("💉 Child Immunization Dashboard")
    st.markdown("Monitor health outcomes, vaccine coverage, and fully immunized children.")
    
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    start_month, end_month = st.select_slider("Select Month Range", options=months, value=("Jan", "Dec"))
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👶 Birth Doses (BCG/HepB)", 
        "🛡️ Penta (DPT-HiB-HepB)", 
        "💧 Polio (OPV/IPV)", 
        "🫁 Pneumococcal (PCV)", 
        "🎯 MMR & FIC"
    ])
    
    with tab1:
        st.header("CPAB, BCG, and Hepa B Coverage")
        if "CPAB_BCG_HepB" in st.session_state['fhsis_data']:
            df = st.session_state['fhsis_data']["CPAB_BCG_HepB"]
            st.success("Data loaded successfully!")
            st.dataframe(df.head(15), use_container_width=True)
            # We will build the exact charts here in the next step!
        else:
            st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")

    with tab2:
        st.header("Pentavalent Vaccine (DPT-HiB-HepB)")
        if "Penta" in st.session_state['fhsis_data']:
            st.dataframe(st.session_state['fhsis_data']["Penta"].head(10))
        else:
            st.info("No data uploaded yet.")

    with tab3:
        st.header("Polio Vaccines (OPV & IPV)")
        if "Polio" in st.session_state['fhsis_data']:
            st.dataframe(st.session_state['fhsis_data']["Polio"].head(10))
        else:
            st.info("No data uploaded yet.")

    with tab4:
        st.header("Pneumococcal Conjugate Vaccine (PCV)")
        if "PCV" in st.session_state['fhsis_data']:
            st.dataframe(st.session_state['fhsis_data']["PCV"].head(10))
        else:
            st.info("No data uploaded yet.")

    with tab5:
        st.header("Measles, FIC, and CIC")
        if "MMR" in st.session_state['fhsis_data']:
            st.dataframe(st.session_state['fhsis_data']["MMR"].head(10))
        else:
            st.info("No data uploaded yet.")

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.markdown("Upload your FHSIS Excel/CSV files here to populate the dashboard.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        file_cpab = st.file_uploader("Upload: 1 CPAB, BCG and Hepa B", type=["csv", "xlsx"])
        if file_cpab:
            st.session_state['fhsis_data']["CPAB_BCG_HepB"] = load_and_clean_fhsis_data(file_cpab)
            
        file_penta = st.file_uploader("Upload: 2 DPT-HiB-HepB", type=["csv", "xlsx"])
        if file_penta:
            st.session_state['fhsis_data']["Penta"] = load_and_clean_fhsis_data(file_penta)
            
        file_polio = st.file_uploader("Upload: 3 OPV and IPV", type=["csv", "xlsx"])
        if file_polio:
            st.session_state['fhsis_data']["Polio"] = load_and_clean_fhsis_data(file_polio)
            
    with col2:
        file_pcv = st.file_uploader("Upload: 4 PCV", type=["csv", "xlsx"])
        if file_pcv:
            st.session_state['fhsis_data']["PCV"] = load_and_clean_fhsis_data(file_pcv)
            
        file_mmr = st.file_uploader("Upload: 5 MMR, FIC and CIC", type=["csv", "xlsx"])
        if file_mmr:
            st.session_state['fhsis_data']["MMR"] = load_and_clean_fhsis_data(file_mmr)
            
    if st.button("Save & Go to Dashboard"):
        st.success("Files processed successfully!")
