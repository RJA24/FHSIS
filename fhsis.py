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
    Cleans the multi-header FHSIS Excel/CSV files by reading all monthly sheets,
    cleaning them, and combining them into a single flat pandas DataFrame.
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            # Fallback for single CSVs
            df = pd.read_csv(uploaded_file, skiprows=4, header=[0, 1])
            sheets_to_process = {"Jan": df} 
        else:
            # For Excel files, read all sheets
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            
            # Look for sheets that represent months (ignore Q1, Q2, 2025, Elig Pop)
            valid_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            for sheet in xls.sheet_names:
                # Check if the sheet name contains a month and is not a Quarter summary
                if any(month.lower() in sheet.lower() for month in valid_months) and "Q" not in sheet:
                    # Load just that month's sheet
                    df_sheet = pd.read_excel(xls, sheet_name=sheet, skiprows=4, header=[0, 1])
                    sheets_to_process[sheet] = df_sheet

        all_months_data = []
        
        for sheet_name, df in sheets_to_process.items():
            # 1. Fix "Merged Cells" issue by forward-filling the top header
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

            # 2. Standardize the Area column
            df.rename(columns={df.columns[0]: 'Area'}, inplace=True)
            
            # 3. Clean up rows: Drop empty regions or repeated headers
            df.dropna(subset=['Area'], inplace=True)
            df = df[~df['Area'].astype(str).str.contains('Area|Interpretation|Recommendation', na=False, case=False)]
            
            # 4. Attach the Month column (First 3 letters of the sheet name, e.g., "Jan", "Sep")
            month_val = sheet_name[:3].capitalize()
            if month_val == "Sep": month_val = "Sep" # Ensure Sept is just Sep
            df['Month'] = month_val
            
            # 5. Convert all data to numbers
            for col in df.columns:
                if col not in ['Area', 'Month', 'Interpretation', 'Recommendation/Actions Taken']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            all_months_data.append(df)
        
        # If we couldn't find any monthly sheets, throw an error
        if not all_months_data:
            raise ValueError("Could not find monthly sheets (Jan, Feb, etc.) in the file.")

        # Stitch all months together into one master dataframe
        final_df = pd.concat(all_months_data, ignore_index=True)
        return final_df

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
            help="This selection isolates columns ending in Total, Male, or Female."
        )

# --- SESSION STATE TO STORE UPLOADED DATA ---
if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = {}

# --- HELPER FUNCTION TO FILTER DATA ---
def filter_data(df, start_month, end_month, gender):
    """Filters the dataframe based on the selected month range and gender."""
    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Filter by Month
    start_idx = months_order.index(start_month)
    end_idx = months_order.index(end_month)
    valid_months = months_order[start_idx:end_idx+1]
    filtered_df = df[df['Month'].isin(valid_months)]
    
    # Filter columns by Gender (Keep Area and Month, plus columns ending with selected gender or no gender specified)
    cols_to_keep = ['Area', 'Month']
    for col in filtered_df.columns:
        if col.endswith(f"_{gender}") or col in ['Interpretation', 'Recommendation/Actions Taken'] or "%" in col:
            cols_to_keep.append(col)
            
    # If the file didn't have specific demographic columns, fallback gracefully
    if len(cols_to_keep) > 2:
        return filtered_df[cols_to_keep]
    return filtered_df

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
            raw_df = st.session_state['fhsis_data']["CPAB_BCG_HepB"]
            filtered_df = filter_data(raw_df, start_month, end_month, gender_filter)
            st.success(f"Displaying data for {start_month}-{end_month} ({gender_filter})")
            st.dataframe(filtered_df.head(15), use_container_width=True)
            # Charts will go here in the next step!
        else:
            st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")

    with tab2:
        st.header("Pentavalent Vaccine (DPT-HiB-HepB)")
        if "Penta" in st.session_state['fhsis_data']:
            raw_df = st.session_state['fhsis_data']["Penta"]
            st.dataframe(filter_data(raw_df, start_month, end_month, gender_filter).head(15), use_container_width=True)
        else:
            st.info("No data uploaded yet.")

    with tab3:
        st.header("Polio Vaccines (OPV & IPV)")
        if "Polio" in st.session_state['fhsis_data']:
            raw_df = st.session_state['fhsis_data']["Polio"]
            st.dataframe(filter_data(raw_df, start_month, end_month, gender_filter).head(15), use_container_width=True)
        else:
            st.info("No data uploaded yet.")

    with tab4:
        st.header("Pneumococcal Conjugate Vaccine (PCV)")
        if "PCV" in st.session_state['fhsis_data']:
            raw_df = st.session_state['fhsis_data']["PCV"]
            st.dataframe(filter_data(raw_df, start_month, end_month, gender_filter).head(15), use_container_width=True)
        else:
            st.info("No data uploaded yet.")

    with tab5:
        st.header("Measles, FIC, and CIC")
        if "MMR" in st.session_state['fhsis_data']:
            raw_df = st.session_state['fhsis_data']["MMR"]
            st.dataframe(filter_data(raw_df, start_month, end_month, gender_filter).head(15), use_container_width=True)
        else:
            st.info("No data uploaded yet.")

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.markdown("Upload your FHSIS Excel/CSV files here to populate the dashboard. You must upload the original multi-sheet Excel files for full functionality.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        file_cpab = st.file_uploader("Upload: 1 CPAB, BCG and Hepa B", type=["csv", "xlsx"])
        if file_cpab:
            df = load_and_clean_fhsis_data(file_cpab)
            if df is not None: st.session_state['fhsis_data']["CPAB_BCG_HepB"] = df
            
        file_penta = st.file_uploader("Upload: 2 DPT-HiB-HepB", type=["csv", "xlsx"])
        if file_penta:
            df = load_and_clean_fhsis_data(file_penta)
            if df is not None: st.session_state['fhsis_data']["Penta"] = df
            
        file_polio = st.file_uploader("Upload: 3 OPV and IPV", type=["csv", "xlsx"])
        if file_polio:
            df = load_and_clean_fhsis_data(file_polio)
            if df is not None: st.session_state['fhsis_data']["Polio"] = df
            
    with col2:
        file_pcv = st.file_uploader("Upload: 4 PCV", type=["csv", "xlsx"])
        if file_pcv:
            df = load_and_clean_fhsis_data(file_pcv)
            if df is not None: st.session_state['fhsis_data']["PCV"] = df
            
        file_mmr = st.file_uploader("Upload: 5 MMR, FIC and CIC", type=["csv", "xlsx"])
        if file_mmr:
            df = load_and_clean_fhsis_data(file_mmr)
            if df is not None: st.session_state['fhsis_data']["MMR"] = df
            
    if st.button("Save Data & Go to Dashboard"):
        st.success("Files processed successfully! Please select '📊 Dashboard' from the left sidebar to view.")
