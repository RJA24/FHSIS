import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FHSIS Immunization Dashboard", page_icon="💉", layout="wide")

# --- LIST OF 27 ABRA RHUs ---
ABRA_RHUS = [
    "Bangued", "Boliney", "Bucay", "Bucloc", "Daguioman", "Danglas", 
    "Dolores", "La Paz", "Lacub", "Lagangilang", "Lagayan", "Langiden", 
    "Licuan-Baay", "Luba", "Malibcong", "Manabo", "Penarrubia", "Pidigan", 
    "Pilar", "Sallapadan", "San Isidro", "San Juan", "San Quintin", 
    "Tayum", "Tineg", "Tubo", "Villaviciosa"
]

# --- DATA CLEANING FUNCTION ---
@st.cache_data
def load_and_clean_fhsis_data(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            sheets_to_process = {"Jan": df_raw} 
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            valid_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            for sheet in xls.sheet_names:
                if any(month.lower() in sheet.lower() for month in valid_months) and "Q" not in sheet and "202" not in sheet:
                    sheets_to_process[sheet] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        
        for sheet_name, df in sheets_to_process.items():
            area_row_idx = -1
            for idx, row in df.iterrows():
                if any('Area' in str(val).strip() for val in row.values if pd.notna(val)):
                    area_row_idx = idx
                    break
                    
            if area_row_idx == -1:
                continue 
                
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 5, len(df))):
                row = df.iloc[idx]
                if any(str(val).strip() in ['Male', 'Female'] for val in row.values if pd.notna(val)):
                    sub_row_idx = idx
                    break

            main_headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], np.nan, regex=True).ffill()
            if sub_row_idx != -1:
                sub_headers = df.iloc[sub_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True)
            else:
                sub_headers = pd.Series([''] * len(main_headers))

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

            seen = set()
            unique_cols = []
            for c in flat_cols:
                if not c:
                    unique_cols.append("")
                    continue
                new_c = c
                counter = 1
                while new_c in seen:
                    new_c = f"{c}_{counter}"
                    counter += 1
                seen.add(new_c)
                unique_cols.append(new_c)

            start_data_idx = sub_row_idx + 1 if sub_row_idx != -1 else area_row_idx + 1
            df_clean = df.iloc[start_data_idx:].copy()
            df_clean.columns = unique_cols
            df_clean = df_clean.loc[:, df_clean.columns != '']

            first_col = df_clean.columns[0]
            if first_col != 'Area':
                if 'Area' in df_clean.columns:
                    df_clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            
            df_clean.dropna(subset=['Area'], inplace=True)
            
            df_clean['Area_Clean'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area_Clean'].isin(ABRA_RHUS)]
            df_clean['Area'] = df_clean['Area_Clean']
            df_clean.drop(columns=['Area_Clean'], inplace=True)

            sheet_lower = sheet_name.lower()
            if "jan" in sheet_lower: month_val = "Jan"
            elif "feb" in sheet_lower: month_val = "Feb"
            elif "mar" in sheet_lower: month_val = "Mar"
            elif "apr" in sheet_lower: month_val = "Apr"
            elif "may" in sheet_lower: month_val = "May"
            elif "jun" in sheet_lower: month_val = "Jun"
            elif "jul" in sheet_lower: month_val = "Jul"
            elif "aug" in sheet_lower: month_val = "Aug"
            elif "sep" in sheet_lower: month_val = "Sep"
            elif "oct" in sheet_lower: month_val = "Oct"
            elif "nov" in sheet_lower: month_val = "Nov"
            elif "dec" in sheet_lower: month_val = "Dec"
            else: month_val = "Unknown"
            
            df_clean['Month'] = month_val
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Interpretation', 'Recommendation/Actions Taken']:
                    if isinstance(df_clean[col], pd.DataFrame):
                        df_clean[col] = pd.to_numeric(df_clean[col].iloc[:, 0], errors='coerce').fillna(0)
                    else:
                        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

            all_months_data.append(df_clean)
        
        if not all_months_data:
            raise ValueError("Could not find properly formatted monthly sheets in the file.")

        return pd.concat(all_months_data, ignore_index=True)

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
        gender_filter = st.selectbox("Select Demographic", options=["Total", "Male", "Female"])

if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = {}

# --- HELPER FUNCTIONS ---
def filter_data(df, start_month, end_month, gender):
    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    start_idx = months_order.index(start_month)
    end_idx = months_order.index(end_month)
    valid_months = months_order[start_idx:end_idx+1]
    filtered_df = df[df['Month'].isin(valid_months)]
    
    cols_to_keep = ['Area', 'Month']
    for col in filtered_df.columns:
        if col.endswith(f"_{gender}") or col in ['Interpretation', 'Recommendation/Actions Taken'] or "%" in col:
            cols_to_keep.append(col)
            
    if len(cols_to_keep) > 2:
        return filtered_df[cols_to_keep]
    return filtered_df

def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        filtered_df = filter_data(raw_df, start_m, end_m, gender)
        
        # Identify columns to plot
        cols_to_plot = []
        for base in base_metrics:
            for col in filtered_df.columns:
                if base in col and col.endswith(f"_{gender}"):
                    cols_to_plot.append(col)
                    break
        
        if cols_to_plot:
            agg_df = filtered_df.groupby('Area')[cols_to_plot].sum().reset_index()
            melted = agg_df.melt(id_vars='Area', value_vars=cols_to_plot, var_name='Vaccine/Antigen', value_name='Count')
            melted['Vaccine/Antigen'] = melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
            
            # --- UPDATED PLOTLY GRAPH WITH DATA LABELS ---
            fig = px.bar(melted, x='Area', y='Count', color='Vaccine/Antigen', barmode='group',
                         title=f"{tab_title} Coverage by RHU ({start_m} - {end_m})",
                         text_auto=True, # This turns on the data labels!
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            
            # Formatting the labels to sit cleanly outside the bars
            fig.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
            
            # Adjusting layout to give the labels room at the top
            fig.update_layout(
                xaxis_title="Rural Health Unit (RHU)", 
                yaxis_title="Number of Children", 
                legend_title="Antigen",
                margin=dict(t=60) # Gives a little extra breathing room at the top
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View Filtered Data Table"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")

# --- MAIN DASHBOARD PAGE ---
if page == "📊 Dashboard":
    st.title("💉 Child Immunization Dashboard - Abra Province")
    
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
        st.header("CPAB, BCG, and Hepa B")
        render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG (0-28 days)", "HepB, within 24 hours"], start_month, end_month, gender_filter)

    with tab2:
        st.header("Pentavalent Vaccine (DPT-HiB-HepB)")
        render_tab_content("Pentavalent", "Penta", ["DPT-HiB-HepB 1", "DPT-HiB-HepB 2", "DPT-HiB-HepB 3"], start_month, end_month, gender_filter)

    with tab3:
        st.header("Polio Vaccines (OPV & IPV)")
        render_tab_content("Polio", "Polio", ["OPV 1", "OPV 2", "OPV 3", "IPV 1", "IPV 2"], start_month, end_month, gender_filter)

    with tab4:
        st.header("Pneumococcal Conjugate Vaccine (PCV)")
        render_tab_content("Pneumococcal", "PCV", ["PCV 1", "PCV 2", "PCV 3"], start_month, end_month, gender_filter)

    with tab5:
        st.header("Measles, FIC, and CIC")
        render_tab_content("MMR & Fully Immunized Children", "MMR", ["MMR 1", "MMR 2", "FIC"], start_month, end_month, gender_filter)

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.markdown("Upload your FHSIS Excel files here. The app extracts all 12 monthly sheets and filters for Abra's 27 RHUs automatically.")
    
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
