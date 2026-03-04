import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

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

# --- GSHEETS CONFIGURATION ---
# We will create one worksheet per dataset inside your master Google Sheet
SHEET_MAPPING = {
    "CPAB_BCG_HepB": "CPAB_Data",
    "Penta": "Penta_Data",
    "Polio": "Polio_Data",
    "PCV": "PCV_Data",
    "MMR": "MMR_Data"
}

def load_data_from_gsheets():
    """Pulls permanent data from Google Sheets."""
    loaded_data = {}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        for app_key, sheet_name in SHEET_MAPPING.items():
            # Read data, gracefully ignore if the sheet is empty or missing
            try:
                df = conn.read(worksheet=sheet_name, ttl=600) # Caches for 10 minutes
                if not df.empty and 'Area' in df.columns:
                    loaded_data[app_key] = df
            except Exception:
                pass 
    except Exception as e:
        st.error("Google Sheets connection not fully configured yet. Please check your secrets.toml file.")
    return loaded_data

def save_data_to_gsheets(data_dict):
    """Pushes the uploaded FHSIS data permanently to Google Sheets."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    for app_key, df in data_dict.items():
        sheet_name = SHEET_MAPPING[app_key]
        with st.spinner(f"Saving {app_key} to cloud database..."):
            conn.update(worksheet=sheet_name, data=df)

# --- SUPER INTELLIGENT DATA PARSER (2026 READY) ---
@st.cache_data
def load_and_clean_fhsis_data(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            sheets_to_process = {"Jan": df_raw} 
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            
            for sheet in xls.sheet_names:
                clean_sheet_name = sheet.lower().strip()
                # Intelligent month matching (ignores random text/years added to the tab name)
                for month in valid_months:
                    if month in clean_sheet_name and "q" not in clean_sheet_name and "annual" not in clean_sheet_name:
                        sheets_to_process[month.capitalize()] = pd.read_excel(xls, sheet_name=sheet, header=None)
                        break

        all_months_data = []
        # Dynamic keywords to find the data anchor in future templates
        anchor_keywords = ['area', 'municipality', 'city/municipality', 'city / municipality', 'rhu', 'lgu']
        
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            
            # 1. Fuzzy Anchor Search
            for idx, row in df.iterrows():
                row_str = " ".join(str(val).lower().strip() for val in row.values if pd.notna(val))
                if any(keyword in row_str for keyword in anchor_keywords):
                    area_row_idx = idx
                    break
                    
            if area_row_idx == -1:
                continue 
                
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 6, len(df))):
                row_str = " ".join(str(val).lower().strip() for val in row.values if pd.notna(val))
                if 'male' in row_str or 'female' in row_str:
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
            if first_col.lower() not in anchor_keywords:
                if 'Area' in df_clean.columns:
                    df_clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            else:
                df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            
            df_clean.dropna(subset=['Area'], inplace=True)
            
            df_clean['Area_Clean'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area_Clean'].isin(ABRA_RHUS)]
            df_clean['Area'] = df_clean['Area_Clean']
            df_clean.drop(columns=['Area_Clean'], inplace=True)

            df_clean['Month'] = month_val
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Interpretation', 'Recommendation/Actions Taken']:
                    if isinstance(df_clean[col], pd.DataFrame):
                        df_clean[col] = pd.to_numeric(df_clean[col].iloc[:, 0], errors='coerce').fillna(0)
                    else:
                        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

            all_months_data.append(df_clean)
        
        if not all_months_data:
            raise ValueError("Could not extract data. The template format may have changed too drastically.")

        return pd.concat(all_months_data, ignore_index=True)

    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("FHSIS App")
    page = st.radio("Navigation", ["📊 Dashboard", "📁 Data Uploader"])
    st.markdown("---")
    
    if page == "📊 Dashboard":
        st.subheader("Global Filters")
        gender_filter = st.selectbox("Select Demographic", options=["Total", "Male", "Female"])

# --- INITIALIZE SESSION STATE FROM GOOGLE SHEETS ---
if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = load_data_from_gsheets()

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

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        filtered_df = filter_data(raw_df, start_m, end_m, gender)
        
        cols_to_plot = []
        for base in base_metrics:
            for col in filtered_df.columns:
                if base in col and col.endswith(f"_{gender}"):
                    cols_to_plot.append(col)
                    break
        
        if cols_to_plot:
            agg_df = filtered_df.groupby('Area')[cols_to_plot].sum().reset_index()
            safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
            
            st.markdown("#### 🏆 Province-Wide Summary")
            kpi_cols = st.columns(len(cols_to_plot))
            for i, col in enumerate(cols_to_plot):
                total_val = int(agg_df[col].sum())
                clean_name = col.replace(f"_{gender}", "")
                with kpi_cols[i]:
                    st.metric(label=f"Total {clean_name}", value=f"{total_val:,}")
            
            st.markdown("---")
            
            st.markdown(f"#### 📈 {tab_title} - Abra Province Total")
            abra_total_df = agg_df[cols_to_plot].sum().reset_index()
            abra_total_df.columns = ['Vaccine/Antigen', 'Count']
            abra_total_df['Vaccine/Antigen'] = abra_total_df['Vaccine/Antigen'].str.replace(f"_{gender}", "")
            
            fig_abra = px.bar(abra_total_df, x='Vaccine/Antigen', y='Count', color='Vaccine/Antigen',
                              title=f"Abra Province Total ({start_m} - {end_m})",
                              text_auto=True,
                              color_discrete_sequence=px.colors.qualitative.Pastel)
            
            fig_abra.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
            fig_abra.update_layout(xaxis_title="Antigen", yaxis_title="Number of Children", showlegend=False, margin=dict(t=60))
            
            config_abra = {'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_Provincial_Total_{safe_filename}', 'height': 600, 'width': 1000, 'scale': 4}}
            st.plotly_chart(fig_abra, use_container_width=True, config=config_abra)

            st.markdown("---")
            
            st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
            melted = agg_df.melt(id_vars='Area', value_vars=cols_to_plot, var_name='Vaccine/Antigen', value_name='Count')
            melted['Vaccine/Antigen'] = melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
            
            fig_rhu = px.bar(melted, x='Area', y='Count', color='Vaccine/Antigen', barmode='group',
                         title=f"RHU Breakdown ({start_m} - {end_m})",
                         text_auto=True,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            
            fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
            fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Number of Children", legend_title="Antigen", margin=dict(t=60))
            
            config_rhu = {'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_RHU_Breakdown_{safe_filename}', 'height': 600, 'width': 1200, 'scale': 4}}
            st.plotly_chart(fig_rhu, use_container_width=True, config=config_rhu)
            
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View & Download Filtered Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_Data_{start_m}_to_{end_m}.csv", mime="text/csv")
    else:
        st.info("No data available. Please go to the Data Uploader page to add files.")

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
        render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG (0-28 days)", "HepB, within 24 hours"], start_month, end_month, gender_filter)

    with tab2:
        render_tab_content("Pentavalent", "Penta", ["DPT-HiB-HepB 1", "DPT-HiB-HepB 2", "DPT-HiB-HepB 3"], start_month, end_month, gender_filter)

    with tab3:
        render_tab_content("Polio", "Polio", ["OPV 1", "OPV 2", "OPV 3", "IPV 1", "IPV 2"], start_month, end_month, gender_filter)

    with tab4:
        render_tab_content("Pneumococcal", "PCV", ["PCV 1", "PCV 2", "PCV 3"], start_month, end_month, gender_filter)

    with tab5:
        render_tab_content("MMR and FIC", "MMR", ["MMR 1", "MMR 2", "FIC"], start_month, end_month, gender_filter)

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.markdown("Upload FHSIS Excel files. The intelligent parser will clean the data and sync it directly to Google Sheets.")
    
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
            
    st.markdown("---")
    
    if st.button("☁️ Sync Data to Google Sheets", type="primary", use_container_width=True):
        if st.session_state['fhsis_data']:
            save_data_to_gsheets(st.session_state['fhsis_data'])
            st.success("✅ Files successfully synced to Google Sheets! The dashboard is now permanently updated.")
        else:
            st.error("No data uploaded yet to save.")
