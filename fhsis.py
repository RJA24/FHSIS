import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FHSIS Immunization Dashboard", page_icon="💉", layout="wide")

# --- GSHEETS CONFIGURATION ---
# We will create one worksheet per dataset inside your master Google Sheet
SHEET_MAPPING = {
    "CPAB_BCG_HepB": "CPAB_Data",
    "Penta": "Penta_Data",
    "Polio": "Polio_Data",
    "PCV": "PCV_Data",
    "MMR": "MMR_Data"
}

def save_data_to_gsheets(data_dict):
    """Pushes the uploaded FHSIS data permanently to Google Sheets."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    for app_key, df in data_dict.items():
        sheet_name = SHEET_MAPPING[app_key]
        with st.spinner(f"Saving {app_key} to cloud database..."):
            conn.update(worksheet=sheet_name, data=df)

def load_data_from_gsheets():
    """Pulls permanent data from Google Sheets."""
    loaded_data = {}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        for app_key, sheet_name in SHEET_MAPPING.items():
            try:
                # ttl=0 forces it to grab fresh data on refresh
                df = conn.read(worksheet=sheet_name, ttl=0) 
                if not df.empty and 'Area' in df.columns:
                    loaded_data[app_key] = df
            except Exception:
                pass 
    except Exception as e:
        st.error("Google Sheets connection not fully configured yet. Please check your secrets.toml file.")
    return loaded_data

def clear_session_data():
    """Wipes the current session data (Note: Does not delete from GSheets)."""
    st.session_state['fhsis_data'] = {}

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
            fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Number of Children", legend_title="Antigen", margin=dict(t=6
