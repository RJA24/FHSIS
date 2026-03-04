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
    Cleans the FHSIS Excel/CSV files by dynamically searching for header rows 
    to bypass formatting inconsistencies and blank rows.
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            # Read blindly without headers first to search for them
            df_raw = pd.read_csv(uploaded_file, header=None)
            sheets_to_process = {"Jan": df_raw} 
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            valid_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            for sheet in xls.sheet_names:
                if any(month.lower() in sheet.lower() for month in valid_months) and "Q" not in sheet:
                    sheets_to_process[sheet] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        
        for sheet_name, df in sheets_to_process.items():
            # 1. Dynamically find the row containing "Area"
            area_row_idx = -1
            for idx, row in df.iterrows():
                if any('Area' in str(val).strip() for val in row.values if pd.notna(val)):
                    area_row_idx = idx
                    break
                    
            if area_row_idx == -1:
                continue # Skip this sheet if no 'Area' column is found
                
            # 2. Find row with "Male" or "Female" directly below "Area"
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 5, len(df))):
                row = df.iloc[idx]
                if any(str(val).strip() in ['Male', 'Female'] for val in row.values if pd.notna(val)):
                    sub_row_idx = idx
                    break

            # 3. Extract Main Headers and forward-fill merged cells
            main_headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], np.nan, regex=True).ffill()
            
            # Extract Sub Headers (Male/Female/Total/%)
            if sub_row_idx != -1:
                sub_headers = df.iloc[sub_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True)
            else:
                sub_headers = pd.Series([''] * len(main_headers))

            # Combine top and bottom headers cleanly
            flat_cols = []
            for top, bot in zip(main_headers, sub_headers):
                top_str = str(top).strip().replace('\n', ' ') if pd.notna(top) and str(top) != 'nan' else ""
                bot_str = str(bot).strip().replace('\n', ' ') if bot and str(bot) != 'nan' else ""
                
                if bot_str and bot_str not in top_str and top_str:
                    flat_cols.append(f"{top_str}_{bot_str}")
                elif top_str:
                    flat_cols.append(top_str)
                else:
                    flat_cols.append(bot_str)

            # 4. Slice the actual data starting beneath the headers
            start_data_idx = sub_row_idx + 1 if sub_row_idx != -1 else area_row_idx + 1
            df_clean = df.iloc[start_data_idx:].copy()
            df_clean.columns = flat_cols
            
            # 5. Drop any empty or duplicated garbage columns
            df_clean = df_clean.loc[:, df_clean.columns != '']
            df_clean = df_clean.loc[:, ~df_clean.columns.duplicated()]

            # Standardize 'Area' column name
            first_col = df_clean.columns[0]
            df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            
            # Drop empty regions or repeated headers that snuck into the data
            df_clean.dropna(subset=['Area'], inplace=True)
            df_clean = df_clean[~df_clean['Area'].astype(str).str.contains('Area|Interpretation|Recommendation|NaN', na=False, case=False)]
            
            # Attach the specific Month for the slider filter
            month_val = sheet_name[:3].capitalize()
            if month_val == "Sep": month_val = "Sep"
            df_clean['Month'] = month_val
            
            # 6. Convert to pure numbers for graphing
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Interpretation', 'Recommendation/Actions Taken']:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

            all_months_data.append(df_clean)
        
        if not all_months_data:
            raise ValueError("Could not find properly formatted monthly sheets in the file.")

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
    
    # Filter columns by Gender
    cols_to_keep = ['Area', 'Month']
    for col in filtered_df.columns:
        if col.endswith(f"_{gender}") or col in ['Interpretation', 'Recommendation/Actions Taken'] or "%" in col:
            cols_to_keep.append(col)
            
    # Fallback gracefully if no specific demographics found
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
