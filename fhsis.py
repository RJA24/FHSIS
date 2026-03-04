import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Abra FHSIS Dashboard", page_icon="💉", layout="wide")

# --- LIST OF 27 ABRA RHUs ---
ABRA_RHUS = [
    "Bangued", "Boliney", "Bucay", "Bucloc", "Daguioman", "Danglas", 
    "Dolores", "La Paz", "Lacub", "Lagangilang", "Lagayan", "Langiden", 
    "Licuan-Baay", "Luba", "Malibcong", "Manabo", "Penarrubia", "Pidigan", 
    "Pilar", "Sallapadan", "San Isidro", "San Juan", "San Quintin", 
    "Tayum", "Tineg", "Tubo", "Villaviciosa"
]

# --- GSHEETS CONFIGURATION ---
SHEET_MAPPING = {
    "CPAB_BCG_HepB": "CPAB_Data",
    "Penta": "Penta_Data",
    "Polio": "Polio_Data",
    "PCV": "PCV_Data",
    "MMR": "MMR_Data"
}

def load_data_from_gsheets():
    loaded_data = {}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        for app_key, sheet_name in SHEET_MAPPING.items():
            try:
                df = conn.read(worksheet=sheet_name, ttl=0) # ttl=0 forces fresh data on refresh
                if not df.empty and 'Area' in df.columns:
                    loaded_data[app_key] = df
            except Exception:
                pass 
    except Exception as e:
        st.error("Connection Error: Check your Streamlit Secrets.")
    return loaded_data

def save_data_to_gsheets(data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    for app_key, df in data_dict.items():
        sheet_name = SHEET_MAPPING[app_key]
        with st.spinner(f"Pushing {app_key} to Google Sheets..."):
            conn.update(worksheet=sheet_name, data=df)

# --- INTELLIGENT PARSER ---
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
                clean_name = sheet.lower().strip()
                for m in valid_months:
                    if m in clean_name and "q" not in clean_name and "annual" not in clean_name:
                        sheets_to_process[m.capitalize()] = pd.read_excel(xls, sheet_name=sheet, header=None)
                        break

        all_months_data = []
        anchor_keywords = ['area', 'municipality', 'rhu', 'lgu']
        
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            for idx, row in df.iterrows():
                row_str = " ".join(str(val).lower().strip() for val in row.values if pd.notna(val))
                if any(kw in row_str for kw in anchor_keywords):
                    area_row_idx = idx
                    break
            
            if area_row_idx == -1: continue
            
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 6, len(df))):
                row_str = " ".join(str(val).lower().strip() for val in row.values if pd.notna(val))
                if 'male' in row_str or 'female' in row_str:
                    sub_row_idx = idx
                    break

            main_headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], np.nan, regex=True).ffill()
            sub_headers = df.iloc[sub_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True) if sub_row_idx != -1 else pd.Series([''] * len(main_headers))

            flat_cols = []
            for top, bot in zip(main_headers, sub_headers):
                t, b = str(top).strip().replace('\n', ' '), str(bot).strip().replace('\n', ' ')
                if b and b not in t and t != 'nan': flat_cols.append(f"{t}_{b}")
                else: flat_cols.append(t if t != 'nan' else b)

            seen = set()
            unique_cols = []
            for c in flat_cols:
                new_c, counter = c, 1
                while new_c in seen:
                    new_c, counter = f"{c}_{counter}", counter + 1
                seen.add(new_c)
                unique_cols.append(new_c)

            df_clean = df.iloc[(sub_row_idx if sub_row_idx != -1 else area_row_idx) + 1:].copy()
            df_clean.columns = unique_cols
            df_clean = df_clean.loc[:, df_clean.columns != '']
            
            first_col = df_clean.columns[0]
            df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            df_clean['Area'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area'].isin(ABRA_RHUS)]
            df_clean['Month'] = month_val
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Interpretation', 'Recommendation/Actions Taken']:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

            all_months_data.append(df_clean)
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"Cleaning Error: {e}")
        return None

# --- UI HELPERS ---
def filter_data(df, start_m, end_m, gender):
    order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    valid = order[order.index(start_m):order.index(end_m)+1]
    f_df = df[df['Month'].isin(valid)]
    cols = ['Area', 'Month'] + [c for c in f_df.columns if c.endswith(f"_{gender}") or "%" in c or c in ['Interpretation', 'Recommendation/Actions Taken']]
    return f_df[cols] if len(cols) > 2 else f_df

def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender):
    # Fix the UnboundLocalError by defining this immediately
    safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
    
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
            st.markdown("#### 🏆 Province-Wide Summary")
            k_cols = st.columns(len(cols_to_plot))
            for i, col in enumerate(cols_to_plot):
                k_cols[i].metric(label=f"Total {col.replace(f'_{gender}', '')}", value=f"{int(agg_df[col].sum()):,}")
            
            # --- CHARTS ---
            abra_sum = agg_df[cols_to_plot].sum().reset_index()
            abra_sum.columns = ['Antigen', 'Count']
            abra_sum['Antigen'] = abra_sum['Antigen'].str.replace(f"_{gender}", "")
            
            fig_p = px.bar(abra_sum, x='Antigen', y='Count', color='Antigen', title=f"Abra Provincial Total ({start_m}-{end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True, config={'toImageButtonOptions': {'scale': 4, 'filename': f'Abra_Total_{safe_filename}'}})
            
            melted = agg_df.melt(id_vars='Area', value_vars=cols_to_plot, var_name='Antigen', value_name='Count')
            melted['Antigen'] = melted['Antigen'].str.replace(f"_{gender}", "")
            fig_r = px.bar(melted, x='Area', y='Count', color='Antigen', barmode='group', title="RHU Breakdown", text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_r, use_container_width=True, config={'toImageButtonOptions': {'scale': 4, 'filename': f'Abra_RHU_{safe_filename}'}})
        else:
            st.warning("No specific columns found for this filter.")

        with st.expander("📄 Data Table & CSV"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, f"Abra_{safe_filename}_{start_m}_{end_m}.csv", "text/csv")
    else:
        st.info("No data synced for this category.")

# --- APP FLOW ---
if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = load_data_from_gsheets()

with st.sidebar:
    st.title("FHSIS Abra")
    page = st.radio("Navigation", ["📊 Dashboard", "📁 Data Uploader"])
    gender_filter = st.selectbox("Demographic", ["Total", "Male", "Female"]) if page == "📊 Dashboard" else "Total"

if page == "📊 Dashboard":
    st.title("💉 Abra Province Immunization Dashboard")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    s_m, e_m = st.select_slider("Time Range", options=months, value=("Jan", "Dec"))
    
    t1, t2, t3, t4, t5 = st.tabs(["👶 Birth", "🛡️ Penta", "💧 Polio", "🫁 PCV", "🎯 MMR/FIC"])
    with t1: render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG (0-28 days)", "HepB, within 24 hours"], s_m, e_m, gender_filter)
    with t2: render_tab_content("Pentavalent", "Penta", ["DPT-HiB-HepB 1", "DPT-HiB-HepB 2", "DPT-HiB-HepB 3"], s_m, e_m, gender_filter)
    with t3: render_tab_content("Polio", "Polio", ["OPV 1", "OPV 2", "OPV 3", "IPV 1", "IPV 2"], s_m, e_m, gender_filter)
    with t4: render_tab_content("Pneumococcal", "PCV", ["PCV 1", "PCV 2", "PCV 3"], s_m, e_m, gender_filter)
    with t5: render_tab_content("MMR and FIC", "MMR", ["MMR 1", "MMR 2", "FIC"], s_m, e_m, gender_filter)

else:
    st.title("📁 Data Uploader")
    c1, c2 = st.columns(2)
    with c1:
        f1 = st.file_uploader("1: Birth Doses", type=["xlsx"])
        if f1: st.session_state['fhsis_data']["CPAB_BCG_HepB"] = load_and_clean_fhsis_data(f1)
        f2 = st.file_uploader("2: Pentavalent", type=["xlsx"])
        if f2: st.session_state['fhsis_data']["Penta"] = load_and_clean_fhsis_data(f2)
        f3 = st.file_uploader("3: Polio", type=["xlsx"])
        if f3: st.session_state['fhsis_data']["Polio"] = load_and_clean_fhsis_data(f3)
    with c2:
        f4 = st.file_uploader("4: PCV", type=["xlsx"])
        if f4: st.session_state['fhsis_data']["PCV"] = load_and_clean_fhsis_data(f4)
        f5 = st.file_uploader("5: MMR/FIC", type=["xlsx"])
        if f5: st.session_state['fhsis_data']["MMR"] = load_and_clean_fhsis_data(f5)

    if st.button("☁️ Sync to Cloud Database", type="primary", use_container_width=True):
        save_data_to_gsheets(st.session_state['fhsis_data'])
        st.success("✅ Synchronized with Google Sheets!")
