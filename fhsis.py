import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FHSIS Immunization Dashboard", page_icon="💉", layout="wide")

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
                df = conn.read(worksheet=sheet_name, ttl=0) 
                if not df.empty and 'Area' in df.columns:
                    # --- CRITICAL: Ignore "Ghost Rows" that have no Year or Area ---
                    df = df.dropna(subset=['Area', 'Year'])
                    loaded_data[app_key] = df
            except Exception:
                pass 
    except Exception as e:
        st.error("Google Sheets connection not fully configured yet.")
    return loaded_data

def save_data_to_gsheets(new_data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    existing_data = load_data_from_gsheets()
    
    for app_key, new_df in new_data_dict.items():
        sheet_name = SHEET_MAPPING[app_key]
        if app_key in existing_data and not existing_data[app_key].empty:
            old_df = existing_data[app_key]
            # Replace existing year data with new upload
            if 'Year' in old_df.columns and 'Year' in new_df.columns:
                upload_years = new_df['Year'].unique()
                old_df = old_df[~old_df['Year'].isin(upload_years)]
            combined_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
            
        with st.spinner(f"Merging {app_key}..."):
            conn.update(worksheet=sheet_name, data=combined_df)

def nuke_cloud_database():
    """Wipes all data and resets headers to kill 'Data Ghosts'."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    for app_key, sheet_name in SHEET_MAPPING.items():
        with st.spinner(f"Resetting {sheet_name}..."):
            # Create a truly clean 1-row header shell
            reset_df = pd.DataFrame(columns=['Area', 'Month', 'Year'])
            conn.update(worksheet=sheet_name, data=reset_df)
    st.session_state['fhsis_data'] = {}

def clear_session_data():
    st.session_state['fhsis_data'] = {}

# --- ABRA RHUs & COORDS ---
ABRA_RHUS = ["Bangued", "Boliney", "Bucay", "Bucloc", "Daguioman", "Danglas", "Dolores", "La Paz", "Lacub", "Lagangilang", "Lagayan", "Langiden", "Licuan-Baay", "Luba", "Malibcong", "Manabo", "Penarrubia", "Pidigan", "Pilar", "Sallapadan", "San Isidro", "San Juan", "San Quintin", "Tayum", "Tineg", "Tubo", "Villaviciosa"]
ABRA_COORDS = {"Bangued": (17.595, 120.613), "Boliney": (17.394, 120.814), "Bucay": (17.541, 120.720), "Bucloc": (17.433, 120.783), "Daguioman": (17.448, 120.822), "Danglas": (17.728, 120.655), "Dolores": (17.647, 120.710), "La Paz": (17.668, 120.672), "Lacub": (17.669, 120.945), "Lagangilang": (17.618, 120.735), "Lagayan": (17.734, 120.730), "Langiden": (17.579, 120.575), "Licuan-Baay": (17.585, 120.884), "Luba": (17.324, 120.698), "Malibcong": (17.564, 120.988), "Manabo": (17.434, 120.702), "Penarrubia": (17.563, 120.648), "Pidigan": (17.572, 120.589), "Pilar": (17.421, 120.595), "Sallapadan": (17.456, 120.763), "San Isidro": (17.468, 120.606), "San Juan": (17.683, 120.738), "San Quintin": (17.544, 120.521), "Tayum": (17.617, 120.665), "Tineg": (17.785, 120.938), "Tubo": (17.234, 120.748), "Villaviciosa": (17.439, 120.632)}

@st.cache_data
def load_and_clean_fhsis_data(uploaded_file, year):
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheets_to_process = {}
        valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        invalid_keywords = ["-", "to", "q", "sem", "annual", "summary", "cons", "ytd"]
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
        
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower().strip()
            found = [m for m in valid_months if m in sheet_lower]
            if len(found) == 1 and not any(inv in sheet_lower for inv in invalid_keywords):
                sheets_to_process[month_map[found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            for idx, row in df.iterrows():
                if any('Area' in str(val).strip() for val in row.values if pd.notna(val)):
                    area_row_idx = idx; break
            if area_row_idx == -1: continue 
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 5, len(df))):
                if any(str(val).strip() in ['Male', 'Female'] for val in df.iloc[idx].values if pd.notna(val)):
                    sub_row_idx = idx; break
            
            headers = df.iloc[area_row_idx].ffill().astype(str).replace(['nan', 'Unnamed:.*'], '', regex=True)
            subs = df.iloc[sub_row_idx].astype(str).replace(['nan', 'Unnamed:.*'], '', regex=True) if sub_row_idx != -1 else pd.Series(['']*len(headers))
            cols = [f"{h}_{s}".strip('_') for h, s in zip(headers, subs)]
            
            clean = df.iloc[max(area_row_idx, sub_row_idx)+1:].copy()
            clean.columns = cols
            clean = clean.loc[:, ~clean.columns.duplicated()]
            clean.rename(columns={clean.columns[0]: 'Area'}, inplace=True)
            clean['Area'] = clean['Area'].astype(str).str.strip()
            clean = clean[clean['Area'].isin(ABRA_RHUS)]
            clean['Month'] = month_val
            clean['Year'] = year
            for col in clean.columns:
                if col not in ['Area', 'Month', 'Year']:
                    clean[col] = pd.to_numeric(clean[col], errors='coerce').fillna(0)
            all_months_data.append(clean)
        return pd.concat(all_months_data, ignore_index=True) if all_months_data else None
    except Exception as e:
        st.error(f"Error: {e}"); return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("FHSIS App")
    page = st.radio("Navigation", ["📊 Dashboard", "📈 YoY Comparison", "📁 Data Uploader"])
    if page != "📁 Data Uploader":
        selected_year = st.selectbox("Select Year", options=[2021, 2022, 2023, 2024, 2025, 2026, 2027], index=4)
        gender_filter = st.selectbox("Select Demographic", options=["Total", "Male", "Female"])

if 'fhsis_data' not in st.session_state:
    st.session_state['fhsis_data'] = load_data_from_gsheets()

def filter_data(df, start_month, end_month, gender, year):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    valid_range = months[months.index(start_month):months.index(end_month)+1]
    df = df[(df['Month'].isin(valid_range)) & (df['Year'] == year)]
    cols = ['Area', 'Month', 'Year']
    for c in df.columns:
        if c in cols: continue
        if gender == "Total":
            if c.endswith("_Total") or not (c.endswith("_Male") or c.endswith("_Female")): cols.append(c)
        elif c.endswith(f"_{gender}"): cols.append(c)
    return df[list(dict.fromkeys(cols))]

def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender, year):
    if df_key in st.session_state['fhsis_data']:
        filtered_df = filter_data(st.session_state['fhsis_data'][df_key], start_m, end_m, gender, year)
        if filtered_df.empty: st.info("No data for selection."); return
        
        elig_cols = [c for c in filtered_df.columns if any(x in c.lower() for x in ['elig', 'pop'])]
        plot_cols = [c for c in filtered_df.columns if any(b.lower() in c.lower() for b in base_metrics) and c not in elig_cols and "%" not in c and c not in ['Area','Month','Year']]
        
        agg_df = filtered_df.groupby('Area').agg({**{c:'sum' for c in plot_cols}, **{c:'max' for c in elig_cols}}).reset_index()
        view_mode = st.radio("Metric", ["Raw Counts", "Percentage (%) Coverage"], horizontal=True, key=f"v_{tab_title}")
        
        # Smart Defaulting
        defaults = [c for c in plot_cols if "total" not in c.replace(f"_{gender}","").lower()]
        with st.expander("⚙️ Add / Remove Indicators"):
            selected = st.multiselect("Indicators", options=plot_cols, default=defaults if defaults else plot_cols, key=f"ms_{tab_title}_{year}")
            
        if selected:
            # Metrics
            cols = st.columns(len(selected))
            for i, c in enumerate(selected):
                val = agg_df[c].sum()
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    pop = agg_df[elig_cols[0]].sum()
                    cols[i].metric(c.replace(f"_{gender}",""), f"{(val/pop*100):.1f}%" if pop>0 else "0%")
                else:
                    cols[i].metric(c.replace(f"_{gender}",""), f"{int(val):,}")

            # Charts
            chart_id = f"{tab_title}_{year}_{time.time()}" # Prevent Duplicate Element ID
            fig = px.bar(agg_df, x='Area', y=selected, barmode='group', title=f"{tab_title} Breakdown")
            st.plotly_chart(fig, use_container_width=True, key=f"bar_{chart_id}")
            
            # Map
            map_df = agg_df.copy()
            map_df['Lat'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[0])
            map_df['Lon'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[1])
            map_df['Val'] = map_df[selected].mean(axis=1)
            fig_map = px.scatter_mapbox(map_df, lat="Lat", lon="Lon", size="Val", color="Val", hover_name="Area", mapbox_style="carto-positron", zoom=8, center={"lat":17.5, "lon":120.7})
            st.plotly_chart(fig_map, use_container_width=True, key=f"map_{chart_id}")

# --- MAIN UI ---
if page == "📊 Dashboard":
    st.title("💉 Abra FHSIS Dashboard")
    st.markdown(f"**Year:** {selected_year} | **Demographic:** {gender_filter}")
    col1, col2 = st.columns([1, 2])
    with col1: time_view = st.radio("Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed")
    with col2:
        if time_view == "Monthly":
            start_month, end_month = st.select_slider("Range", options=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], value=("Jan", "Dec"))
        else:
            q_map = {"Q1":("Jan","Mar"), "Q2":("Apr","Jun"), "Q3":("Jul","Sep"), "Q4":("Oct","Dec")}
            sq, eq = st.select_slider("Range", options=["Q1", "Q2", "Q3", "Q4"], value=("Q1", "Q4"))
            start_month, end_month = q_map[sq][0], q_map[eq][1]
            
    t_exec, t1, t2, t3, t4, t5 = st.tabs(["⭐ Summary", "👶 Birth", "🛡️ Penta", "💧 Polio", "🫁 PCV", "🎯 FIC/CIC"])
    with t_exec:
        if "MMR" in st.session_state['fhsis_data']:
            df = filter_data(st.session_state['fhsis_data']["MMR"], start_month, end_month, gender_filter, selected_year)
            fic_c = next((c for c in df.columns if "FIC" in c and "%" not in c), None)
            pop_c = next((c for c in df.columns if any(x in c.lower() for x in ['elig', 'pop'])), None)
            if fic_c and pop_c:
                res = df.groupby('Area').agg({fic_c:'sum', pop_c:'max'}).reset_index()
                tot_fic, tot_pop = res[fic_c].sum(), res[pop_c].sum()
                cov = (tot_fic/tot_pop*100) if tot_pop > 0 else 0
                c1, c2 = st.columns(2)
                c1.metric("Fully Immunized Child (FIC)", f"{int(tot_fic):,}", f"Cov: {cov:.1f}%")
                if cov > 110: st.warning(f"⚠️ High Coverage Alert: {cov:.1f}% - Check denominator population.")
                
                res['Cov'] = (res[fic_c]/res[pop_c]*100).fillna(0)
                st.plotly_chart(px.bar(res.sort_values('Cov', ascending=False).head(5), x='Area', y='Cov', title="Top 5 RHUs (FIC %)"), use_container_width=True, key="exec_top5")
        else: st.info("Upload MMR data to see summary.")

    with t1: render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG", "Hep"], start_month, end_month, gender_filter, selected_year)
    with t2: render_tab_content("Pentavalent", "Penta", ["Penta", "DPT"], start_month, end_month, gender_filter, selected_year)
    with t3: render_tab_content("Polio", "Polio", ["OPV", "IPV"], start_month, end_month, gender_filter, selected_year)
    with t4: render_tab_content("PCV", "PCV", ["PCV"], start_month, end_month, gender_filter, selected_year)
    with t5: render_tab_content("FIC/CIC", "MMR", ["FIC", "CIC", "MMR"], start_month, end_month, gender_filter, selected_year)

elif page == "📈 YoY Comparison":
    st.title("⚖️ Year-Over-Year Performance")
    y_a = st.selectbox("Baseline Year", [2021,2022,2023,2024,2025,2026], index=3)
    y_b = st.selectbox("Comparison Year", [2021,2022,2023,2024,2025,2026], index=4)
    if y_a == y_b: st.warning("Select different years.")
    else: st.info("Compare performance between years for any antigen in the tabs above.")

elif page == "📁 Data Uploader":
    st.title("Data Uploader")
    u_year = st.selectbox("Year for Upload", [2021,2022,2023,2024,2025,2026])
    files = {k: st.file_uploader(f"Upload {k}", type=["xlsx"]) for k in SHEET_MAPPING.keys()}
    if st.button("☁️ Save to Cloud", type="primary"):
        processed = {k: load_and_clean_fhsis_data(v, u_year) for k, v in files.items() if v}
        if processed:
            save_data_to_gsheets({k: v for k, v in processed.items() if v is not None})
            st.success("Saved! Refreshing..."); time.sleep(1); st.rerun()
            
    with st.expander("⚠️ Database Management"):
        if st.button("🚨 Nuke Cloud Database"):
            nuke_cloud_database()
            st.success("Wiped clean!"); time.sleep(1); st.rerun()
