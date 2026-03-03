def process_uploaded_file(uploaded_file):
    """Processes an in-memory uploaded file from Streamlit (CSV or Excel)."""
    filename = uploaded_file.name
    category = determine_category(filename)
    is_excel = filename.lower().endswith('.xlsx')
    
    # Read the first few rows to find the actual header
    if is_excel:
        temp_df = pd.read_excel(uploaded_file, nrows=20, header=None)
    else:
        temp_df = pd.read_csv(uploaded_file, nrows=20, header=None)
        
    header_row_idx = 0
    for i, row in temp_df.iterrows():
        if any(str(val).strip().lower() == 'area' for val in row.values):
            header_row_idx = i
            break
            
    # Reset file pointer to the beginning before reading the full dataframe
    uploaded_file.seek(0)
    
    if is_excel:
        df = pd.read_excel(uploaded_file, skiprows=header_row_idx)
    else:
        df = pd.read_csv(uploaded_file, skiprows=header_row_idx)
    
    df = clean_fhsis_columns(df)
    
    area_col = [col for col in df.columns if 'area' in str(col).lower()][0]
    df = df.rename(columns={area_col: 'Area'})
    df = df.dropna(subset=['Area'])
    df = df[~df['Area'].astype(str).str.contains('C A R|Interpretation|Recommendation', na=False, case=False)]
    
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

# UPDATE: Allowed types now include 'xlsx'
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
            st.success(f"Successfully normalized {len(uploaded_files)} files into {len(master_db)} rows of data.")
            
            # Show a preview of the clean data
            st.dataframe(master_db.head(10), use_container_width=True)
            
            # Create the download button for the consolidated file
            csv = master_db.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Master Database (CSV)",
                data=csv,
                file_name="Master_FHSIS_Database_2025.csv",
                mime="text/csv",
            )
