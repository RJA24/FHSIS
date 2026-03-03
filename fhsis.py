import streamlit as st
import pandas as pd
import re
import io

# Set up the page layout
st.set_page_config(page_title="FHSIS Data Processor - Abra", layout="wide")
st.title("FHSIS Data Normalization App")
st.markdown("Automated data consolidation for Abra Rural Health Units.")

# Create the Tabs (Starting with Immunization)
tab1, tab2 = st.tabs(["1 Immunization", "More Priorities Coming Soon..."])

# --- HELPER FUNCTIONS ---

def get_period_from_filename(filename):
    """Intelligently extracts the reporting period from the filename."""
    fname = filename.lower()
    if 'elig' in fname or 'pop' in fname: return 'Eligible Population'
    
    # Months
    months = {
        'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
        'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
        'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
    }
    for key, value in months.items():
        if key in fname:
            return value
            
    # Quarters
    if 'q1' in fname or '1st' in fname: return 'Q1'
    if 'q2' in fname or '2nd' in fname: return 'Q2'
    if 'q3' in fname or '3rd' in fname: return 'Q3'
    if 'q4' in fname or '4th' in fname: return 'Q4'
    
    # Annual
    if '2025' in fname or '2026' in fname or 'annual' in fname: return 'Annual'
    
    return 'Unspecified Period'

def get_immunization_category(filename):
    """Categorizes the specific immunization program based on file naming."""
    fname = filename.upper()
    if 'CPAB' in fname or 'BCG' in fname or 'HEPA' in fname or 'HEPB' in fname: return 'CPAB, BCG, HepB'
    if 'DPT' in fname or 'HIB' in fname: return 'DPT-HiB-HepB'
    if 'OPV' in fname or 'IPV' in fname: return 'OPV and IPV'
    if 'PCV' in fname: return 'PCV'
    if 'MMR' in fname or 'FIC' in fname or 'CIC' in fname: return 'MMR, FIC, CIC'
    return 'Other Immunization'

def process_immunization_file(uploaded_file):
    """Reads, cleans, and unpivots FHSIS templates dynamically."""
    filename = uploaded_file.name
    period = get_period_from_filename(filename)
    category = get_immunization_category(filename)
    is_excel = filename.lower().endswith('.xlsx')
    
    # 1. Dynamically locate the header row
    if is_excel:
        temp_df = pd.read_excel(uploaded_file, nrows=20, header=None)
    else:
        temp_df = pd.read_csv(uploaded_file, nrows=20, header=None)
        
    header_row_idx = 0
    for i, row in temp_df.iterrows():
        if any(str(val).strip().lower() == 'area' for val in row.values):
            header_row_idx = i
            break
            
    uploaded_file.seek(0) # Reset file pointer
    
    # 2. Read actual data
    if is_excel:
        df = pd.read_excel(uploaded_file, skiprows=header_row_idx)
    else:
        df = pd.read_csv(uploaded_file, skiprows=header_row_idx)
        
    # 3. Clean complex merged headers (Forward Fill)
    new_cols = []
    current_main = ""
    for col in df.columns:
        if not str(col).startswith('Unnamed'):
            current_main = str(col).strip()
            new_cols.append(current_main)
        else:
            new_cols.append(current_main)
    df.columns = new_cols
    
    # 4. Merge main headers with sub-headers (Male, Female, Total, %)
    first_row = df.iloc[0].fillna('').astype(str).str.strip().str.lower()
    if any(first_row.isin(['male', 'female', 'total', '%', 'no.', 'no'])):
        combined_cols = []
        for main_col, sub_col in zip(df.columns, df.iloc[0]):
            sub_clean = str(sub_col).strip()
            if sub_clean and sub_clean.lower() not in ['nan', 'none']:
                combined_cols.append(f"{main_col} - {sub_clean}")
            else:
                combined_cols.append(main_col)
        df.columns = combined_cols
        df = df.drop(0).reset_index(drop=True)
        
    # 5. Rename Area column and filter strictly for Abra RHUs
    area_col = [col for col in df.columns if 'area' in str(col).lower()][0]
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
    
    # 6. Drop interpretation/recommendation columns
    cols_to_drop = [col for col in df.columns if 'interpretation' in str(col).lower() or 'recommendation' in str(col).lower()]
    df = df.drop(columns=cols_to_drop, errors='ignore')
    
    # 7. Unpivot (Wide to Long) for Power BI Star Schema compatibility
    df_long = pd.melt(df, id_vars=['Area'], var_name='Indicator', value_name='Value')
    
    # Clean values
    df_long['Value'] = pd.to_numeric(df_long['Value'].astype(str).str.replace(',', ''), errors='coerce')
    df_long = df_long.dropna(subset=['Value'])
    
    # 8. Append Metadata
    df_long['Program'] = category
    df_long['Period'] = period
    
    # Extract year from filename if present, otherwise default to 2025
    year_match = re.search(r'(202\d)', filename)
    df_long['Year'] = int(year_match.group(1)) if year_match else 2025
    
    df_long['Source_File'] = filename
    
    return df_long[['Year', 'Period', 'Program', 'Area', 'Indicator', 'Value', 'Source_File']]

# --- TAB 1: IMMUNIZATION ---

with tab1:
    st.subheader("Vaccination & Immunization Processing")
    st.write("Upload your CPAB, BCG, HepB, DPT, OPV, IPV, PCV, MMR, FIC, and CIC CSV/Excel files here.")
    
    uploaded_files = st.file_uploader("Drop Immunization Files", accept_multiple_files=True, type=['csv', 'xlsx'], key="imm_upload")
    
    if uploaded_files:
        if st.button("Process Immunization Data", type="primary"):
            all_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Extracting data from {file.name}...")
                try:
                    cleaned_df = process_immunization_file(file)
                    all_data.append(cleaned_df)
                except Exception as e:
                    st.error(f"Failed to process {file.name}: {e}")
                progress_bar.progress((i + 1) / len(uploaded_files))
                
            status_text.text("Processing complete!")
            
            if all_data:
                master_db = pd.concat(all_data, ignore_index=True)
                st.success(f"Success! Normalized {len(uploaded_files)} files into {len(master_db)} rows of Abra RHU data.")
                
                st.dataframe(master_db.head(10), use_container_width=True)
                
                csv = master_db.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Cleaned Immunization Data (CSV)",
                    data=csv,
                    file_name="Abra_Immunization_Master.csv",
                    mime="text/csv",
                )
