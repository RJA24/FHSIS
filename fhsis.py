import streamlit as st
import pandas as pd
import re
import io

# Set up the page layout
st.set_page_config(page_title="FHSIS Data Processor - Abra Province", layout="wide")
st.title("FHSIS Data Normalization App (Abra RHUs Only)")
st.write("Upload your FHSIS CSV or Excel files to consolidate them into a clean master database for Abra.")

def clean_fhsis_columns(df):
    """Cleans up merged Excel headers that turn into 'Unnamed' in CSVs/Excel."""
    new_cols = []
    current_main = ""
    for col in df.columns:
        if not str(col).startswith('Unnamed'):
            current_main = str(col).strip()
            new_cols.append(current_main)
        else:
            new_cols.append(current_main)
    df.columns = new_cols
    
    first_row = df.iloc[0].fillna('').astype(str).str.strip()
    if any(first_row.str.contains('Male|Female|Total|%', case=False, na=False)):
        combined_cols = []
        for main_col, sub_col in zip(df.columns, first_row):
            if sub_col and sub_col.lower() not in main_col.lower():
                combined_cols.append(f"{main_col} - {sub_col}")
            else:
                combined_cols.append(main_col)
        df.columns = combined_cols
        df = df.drop(0).reset_index(drop=True)
    return df

def extract_period_from_filename(filename):
    """Extracts the reporting period from the filename."""
    filename_lower = filename.lower()
    if re.search(r'q[tr]*\s*1', filename_lower): return 'Q1'
    if re.search(r'q[tr]*\s*2', filename_lower): return 'Q2'
    if re.search(r'q[tr]*\s*3', filename_lower): return 'Q3'
    if re.search(r'q[tr]*\s*4', filename_lower): return 'Q4'
    
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    for m in months:
        if m in filename_lower:
            return m.capitalize()
            
    if 'elig' in filename_lower or 'pop' in filename_lower:
        return 'Eligible Population'
    return 'Annual Summary'

def determine_category(filename):
    """Maps the filename to the correct 8 Priority Health Outcome category."""
    file_categories = {
        '1 4ANC and 8ANC': 'Maternal Health - ANC',
        '7 Pospartum Care': 'Maternal Health - Postpartum',
        '1 Adults Risk Assessed': 'NCD - Adults',
        '2 Seniors Risk Assessed': 'NCD - Seniors',
        '5 Cervical Cancer': 'NCD - Cervical Cancer',
        '6 Breast Cancer': 'NCD - Breast Cancer',
        '1 CPAB, BCG and Hepa B': 'Immunization - Infants',
        '2 DPT-HiB-HepB': 'Immunization - DPT',
        '3 OPV and IPV': 'Immunization - Polio',
        '4 PCV': 'Immunization - PCV',
        '5 MMR, FIC and CIC': 'Immunization - MMR',
        'Env_1 Safe Water': 'Environmental Health - Safe Water',
        'Env_2 Sanitation': 'Environmental Health - Sanitation',
        'F1 Plus 2 Death due to Traffic Injuries': 'Injuries - Traffic'
    }
    for pattern, category in file_categories.items():
        if pattern.lower() in filename.lower():
            return category
    return 'Uncategorized'

def process_uploaded_file(uploaded_file):
    """Processes an in-memory uploaded file and filters strictly for Abra."""
    filename = uploaded_file.name
    category = determine_category(filename)
    is_excel = filename.lower().endswith('.xlsx')
    
    if is_excel:
        temp_df = pd.read_excel(uploaded_file, nrows=20, header=None)
    else:
        temp_df = pd.read_csv(uploaded_file, nrows=20, header=None)
        
    header_row_idx = 0
    for i, row in temp_df.iterrows():
        if any(str(val).strip().lower() == 'area' for val in row.values):
            header_row_idx = i
            break
            
    uploaded_file.seek(0)
    
    if is_excel:
        df = pd.read_excel(uploaded_file, skiprows=header_row_idx)
    else:
        df = pd.read_csv(uploaded_file, skiprows=header_row_idx)
    
    df = clean_fhsis_columns(df)
    
    area_col = [col for col in df.columns if 'area' in str(col).lower()][0]
    df = df.rename(columns={area_col: 'Area'})
    
    # Strip spaces to ensure names like "Boliney " match perfectly
    df['Area'] = df['Area'].astype(str).str.strip()
    
    # --- STRICT ABRA FILTER ---
    abra_rhus = [
        'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas',
        'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden',
        'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan',
        'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin',
        'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
    ]
    df = df[df['Area'].isin(abra_rhus)]
    
    cols_to_drop = [col for col in df.columns if 'interpretation' in str(col).lower() or 'recommendation' in str(col).lower()]
    df = df.drop(columns=cols_to_drop, errors='ignore')
    
    df_long = pd.melt(df, id_vars=['Area'], var_name='Indicator', value_name='Value')
    df_long['Value'] = pd.to_numeric(df_long['Value'].astype(str).str.replace(',', ''), errors='coerce')
    df_long = df_long.dropna(subset=['Value'])
    
    df_long['Period'] = extract_period_from_filename(filename)
    df_long['Year'] = 2025 
    df_long['Health_Outcome'] = category
    df_long['Source_File'] = filename
    
    return df_long[['Year', 'Period', 'Health_Outcome', 'Area', 'Indicator', 'Value', 'Source_File']]

# --- Streamlit UI Components ---

uploaded_files = st.file_uploader("Drop your FHSIS CSV or Excel files here", accept_multiple_files=True, type=['csv', 'xlsx'])

if uploaded_files:
    if st.button("Process Data", type="primary"):
        all_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"Processing {file.name}...")
            try:
                cleaned_df = process_uploaded_file(file)
                all_data.append(cleaned_df)
            except Exception as e:
                st.error(f"Error processing {file.name}: {e}")
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("Consolidation complete!")
        
        if all_data:
            master_db = pd.concat(all_data, ignore_index=True)
            st.success(f"Successfully normalized {len(uploaded_files)} files. Filtered for Abra RHUs only: {len(master_db)} rows generated.")
            
            # Show a preview of the clean data
            st.dataframe(master_db.head(10), use_container_width=True)
            
            # Create the download button for the consolidated file
            csv = master_db.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Abra Master Database (CSV)",
                data=csv,
                file_name="Abra_Master_FHSIS_Database_2025.csv",
                mime="text/csv",
            )
            
            # --- STREAMLIT LIVE DASHBOARD (Track 3) ---
            st.divider()
            st.subheader("📊 Abra RHU Quick Insights")
            
            col1, col2 = st.columns(2)
            with col1:
                outcomes = master_db['Health_Outcome'].dropna().unique()
                selected_outcome = st.selectbox("Filter by Health Outcome:", sorted(outcomes))
            
            with col2:
                filtered_by_outcome = master_db[master_db['Health_Outcome'] == selected_outcome]
                indicators = filtered_by_outcome['Indicator'].dropna().unique()
                selected_indicator = st.selectbox("Filter by Specific Indicator:", sorted(indicators))

            chart_data = filtered_by_outcome[filtered_by_outcome['Indicator'] == selected_indicator]
            
            # Exclude Eligible Population files from the chart to prevent skewed visual scaling
            chart_data = chart_data[chart_data['Period'] != 'Eligible Population']

            if not chart_data.empty:
                # Group by Area to show a comparative bar chart across municipalities
                summary_data = chart_data.groupby(['Area'])['Value'].sum().sort_values(ascending=False)
                
                st.write(f"**Total Reported Values for: {selected_indicator} (Excluding Baseline Population)**")
                st.bar_chart(summary_data)
            else:
                st.info("No reporting data available for the selected filters.")
