import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
st.set_page_config(page_title="Abra FHSIS Dashboard", layout="wide")

# The Master List of Abra Municipalities
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
@st.cache_data
def parse_fhsis_template(uploaded_file):
    """
    Reads the messy DOH template, searches for Abra municipalities,
    and extracts a clean, workable dataframe.
    """
    # Read raw file without headers to avoid multi-index chaos
    df = pd.read_csv(uploaded_file, header=None)
    
    # Clean up string columns (strip whitespace)
    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)

    # Find the column that contains the Area/Municipality names
    area_col_index = None
    for col in df.columns:
        if df[col].astype(str).isin(['Bangued', 'Manabo']).any():
            area_col_index = col
            break
            
    if area_col_index is None:
        return None, "Could not locate Area column."

    # Find the row index where 'Abra' starts and 'Apayao' (the next province) starts
    abra_start = df[df[area_col_index] == 'Abra'].index.min()
    apayao_start = df[df[area_col_index] == 'Apayao'].index.min()

    # Fallback bounds if province headers are missing
    if pd.isna(abra_start): abra_start = 0
    if pd.isna(apayao_start): apayao_start = len(df)

    # Slice out only the Abra section
    abra_df = df.iloc[abra_start:apayao_start].copy()
    
    # Filter only for the main municipality rows (ignores the RHU/Hospital sub-rows for now)
    clean_df = abra_df[abra_df[area_col_index].isin(ABRA_MUNIS)].copy()
    
    # Rename the area column for standard access
    clean_df.rename(columns={area_col_index: 'Municipality'}, inplace=True)
    
    # Drop completely empty columns
    clean_df.dropna(axis=1, how='all', inplace=True)
    
    return clean_df, "Success"

# ---------------------------------------------------------
# APP UI & ROUTING
# ---------------------------------------------------------
st.title("🏥 Abra Provincial FHSIS Dashboard")
st.markdown("Automated ingestion pipeline for 2021-2025 DOH templates.")

# The Dropzone
uploaded_files = st.file_uploader(
    "Drag and drop monthly/quarterly FHSIS CSV templates here", 
    type=['csv', 'xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"{len(uploaded_files)} files loaded into the ingestion engine.")
    
    # Create a tab for every uploaded file
    tabs = st.tabs([file.name[:20] + "..." for file in uploaded_files])
    
    for i, file in enumerate(uploaded_files):
        with tabs[i]:
            st.subheader(f"Data Preview: {file.name}")
            
            # Run the parser
            parsed_data, status = parse_fhsis_template(file)
            
            if parsed_data is not None and not parsed_data.empty:
                # Display the extracted Abra rows
                st.dataframe(parsed_data, use_container_width=True)
                
                # --- Quick Prototyping Feature ---
                st.markdown("### Chart Prototyping")
                st.info("Since FHSIS headers are multi-level, select a column index to visualize:")
                
                # Let user pick a column index to chart (ignoring the Municipality column)
                numeric_cols = [c for c in parsed_data.columns if c != 'Municipality']
                if numeric_cols:
                    selected_col = st.selectbox(f"Select Data Column to chart ({file.name})", numeric_cols, key=f"sel_{i}")
                    
                    # Convert to numeric, forcing errors to NaN, then fill with 0
                    chart_data = parsed_data[['Municipality', selected_col]].copy()
                    chart_data[selected_col] = pd.to_numeric(chart_data[selected_col], errors='coerce').fillna(0)
                    
                    # Sort for better visualization
                    chart_data = chart_data.sort_values(by=selected_col, ascending=False)
                    
                    fig = px.bar(
                        chart_data, 
                        x='Municipality', 
                        y=selected_col,
                        title="Accomplishments by Municipality",
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"Failed to parse file. Error: {status}")
else:
    st.info("Awaiting file upload...")
