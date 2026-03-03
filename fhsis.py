import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------
# 1. CONFIGURATION & TARGETS
# ---------------------------------------------------------
st.set_page_config(page_title="Abra FHSIS Command Center", layout="wide", page_icon="🏥")

# DOH 8-Point Agenda Targets
AGENDA_TARGETS = {
    "1. Immunization": 95.0,     # 95% Full Immunization
    "2. Nutrition": 13.5,        # 13.5% Max Stunting (Lower is better)
    "3. WASH": 100.0,            # 100% Access
    "6. Road Safety": 4.0,       # 4 per 100k (Lower is better)
    "5. TB & HIV": 85.0          # 85% Treatment rate
}

PRIORITY_AGENDA = [
    "1. Immunization", "2. Nutrition", "3. WASH", 
    "4. Maternal Health", "5. TB & HIV", "6. Road Safety", 
    "7. NCDs", "8. Cancer"
]

ABRA_MUNIS = [
    'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 
    'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 
    'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 
    'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 
    'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
]

PERIOD_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Q1": 4, "Apr": 5, "May": 6, "Jun": 7, "Q2": 8, 
    "Jul": 9, "Aug": 10, "Sep": 11, "Sept": 11, "Q3": 12, "Oct": 13, "Nov": 14, "Dec": 15, "Q4": 16, "Annual": 17
}

if 'master_db' not in st.session_state:
    st.session_state.master_db = pd.DataFrame(columns=['Year', 'Tab', 'Period', 'Period_Order', 'Municipality', 'Metric', 'Value'])

# ---------------------------------------------------------
# 2. INTELLIGENT ROUTING & PARSING
# ---------------------------------------------------------
def get_priority_tab(filename):
    name = filename.lower()
    if any(x in name for x in ["cpab", "bcg", "dpt", "opv", "ipv", "pcv", "mmr", "fic", "hpv"]): return "1. Immunization"
    if any(x in name for x in ["mam", "sam", "vitamin a", "mnp", "lns", "low birth", "bf", "stunting"]): return "2. Nutrition"
    if any(x in name for x in ["safe water", "sanitation", "env_"]): return "3. WASH"
    if any(x in name for x in ["4anc", "8anc", "pospartum", "postpartum"]): return "4. Maternal Health"
    if any(x in name for x in ["tb", "hiv"]): return "5. TB & HIV"
    if any(x in name for x in ["traffic", "injuries"]): return "6. Road Safety"
    if any(x in name for x in ["adults risk", "ncd", "hypertensive", "seniors"]): return "7. NCDs"
    if any(x in name for x in ["cervical", "breast", "cancer"]): return "8. Cancer"
    return None

def extract_period(filename):
    match = re.search(r'-\s*([A-Za-z0-9\s]+)\.(csv|xlsx|xls)', filename)
    period = match.group(1).strip() if match else "Annual"
    if "Qtr" in period: period = period.replace("Qtr", "Q")
    return period

def clean_numeric(val):
    if pd.isna(val): return 0.0
    val = str(val).replace(',', '').replace('%', '').strip()
    try: return float(val)
    except: return 0.0

@st.cache_data
def parse_fhsis_template(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            try: df = pd.read_csv(uploaded_file, header=None, encoding='utf-8')
            except: df = pd.read_csv(uploaded_file, header=None, encoding='latin-1')
    except Exception: return None

    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)
    area_col = next((c for c in df.columns if df[c].astype(str).isin(['Bangued', 'Manabo']).any()), None)
    if area_col is None: return None

    car_idx = df[df[area_col] == 'C A R'].index.min()
    abra_idx = df[df[area_col] == 'Abra'].index.min()
    apayao_idx = df[df[area_col] == 'Apayao'].index.min()
    if pd.isna(car_idx): car_idx = max(0, abra_idx - 3)
    if pd.isna(apayao_idx): apayao_idx = len(df)

    h_rows = df.iloc[max(0, int(car_idx)-3):int(car_idx)].copy().ffill(axis=1)
    new_cols = []
    for c in df.columns:
        txts = [str(v) for v in h_rows[c].values if pd.notna(v) and "Unnamed" not in str(v) and "None" not in str(v)]
        name = " | ".join(dict.fromkeys(txts))
        new_cols.append(name if name else f"Col_{c}")
    df.columns = new_cols

    clean_df = df.iloc[int(abra_idx):int(apayao_idx)].copy()
    clean_df = clean_df[clean_df[df.columns[area_col]].isin(ABRA_MUNIS)]
    clean_df.rename(columns={df.columns[area_col]: 'Municipality'}, inplace=True)
    
    final_cols = ['Municipality'] + [c for c in clean_df.columns if 'Total' in c or '%' in c]
    return clean_df[final_cols] if len(final_cols) > 1 else clean_df

# ---------------------------------------------------------
# 3. SIDEBAR CONTROLS
# ---------------------------------------------------------
st.sidebar.title("⚙️ Command Center")
target_year = st.sidebar.selectbox("Assign Year to Uploads:", [2026, 2025, 2024, 2023, 2022, 2021], index=1)

if st.sidebar.button("🗑️ Reset Dashboard Memory"):
    st.session_state.master_db = pd.DataFrame(columns=['Year', 'Tab', 'Period', 'Period_Order', 'Municipality', 'Metric', 'Value'])
    st.rerun()

# ---------------------------------------------------------
# 4. MAIN UPLOAD ENGINE
# ---------------------------------------------------------
st.title("🏥 Abra Provincial FHSIS Command Center")
st.markdown(f"### Performance Tracking: {target_year}")

with st.expander(f"📂 Upload {target_year} Data Batch", expanded=True):
    files = st.file_uploader("Upload CSV/Excel", accept_multiple_files=True)

if files:
    with st.spinner("Processing & updating Master Database..."):
        for f in files:
            if "Elig Pop" in f.name: continue
            tab_name = get_priority_tab(f.name)
            if not tab_name: continue
            
            period = extract_period(f.name)
            data = parse_fhsis_template(f)
            if data is not None:
                m_cols = [c for c in data.columns if c != 'Municipality']
                melted = data.melt(id_vars=['Municipality'], value_vars=m_cols, var_name='Metric', value_name='Value')
                melted['Value'] = melted['Value'].apply(clean_numeric)
                melted[['Year', 'Tab', 'Period', 'Period_Order']] = [target_year, tab_name, period, PERIOD_ORDER.get(period, 99)]
                
                st.session_state.master_db = pd.concat([st.session_state.master_db, melted]).drop_duplicates(
                    subset=['Year', 'Tab', 'Period', 'Municipality', 'Metric'], keep='last'
                )
        st.success(f"Master Database updated with {len(files)} files!")

# ---------------------------------------------------------
# 5. DASHBOARD UI & CHARTS
# ---------------------------------------------------------
db = st.session_state.master_db
if not db.empty:
    tabs = st.tabs(PRIORITY_AGENDA)
    for i, tab_name in enumerate(PRIORITY_AGENDA):
        with tabs[i]:
            tab_data = db[db['Tab'] == tab_name]
            if tab_data.empty:
                st.info(f"Awaiting data for {tab_name}.")
                continue
            
            # --- STATUS CARD LOGIC ---
            metrics = sorted(tab_data['Metric'].unique())
            sum_metric = st.selectbox(f"Key Metric ({tab_name}):", metrics, key=f"sum_{i}")
            
            latest_y = tab_data['Year'].max()
            latest_p_order = tab_data[tab_data['Year'] == latest_y]['Period_Order'].max()
            prov_df = tab_data[(tab_data['Year'] == latest_y) & (tab_data['Period_Order'] == latest_p_order) & (tab_data['Metric'] == sum_metric)]
            latest_p_name = prov_df['Period'].iloc[0] if not prov_df.empty else "Unknown"
            
            val = prov_df['Value'].mean() if '%' in sum_metric else prov_df['Value'].sum()
            target = AGENDA_TARGETS.get(tab_name, 0)
            
            # Color logic for performance
            if target > 0:
                # For stunting or road deaths, lower is better
                if "Nutrition" in tab_name or "Road Safety" in tab_name:
                    status_color = "normal" if val <= target else "inverse"
                else:
                    status_color = "normal" if val >= target else "inverse"
                    
                metric_label = f"Provincial Average" if '%' in sum_metric else f"Provincial Total"
                st.metric(
                    f"🏆 {metric_label} ({latest_p_name} {latest_y})", 
                    f"{val:,.1f}%" if '%' in sum_metric else f"{val:,.0f}", 
                    delta=f"Target: {target}%" if '%' in sum_metric else f"Target: {target}", 
                    delta_color=status_color
                )
            else:
                st.metric(
                    f"🏆 Provincial Total ({latest_p_name} {latest_y})", 
                    f"{val:,.1f}%" if '%' in sum_metric else f"{val:,.0f}"
                )

            st.divider()
            
            # --- TREND ANALYSIS ---
            st.markdown("#### 📈 Timeline Analysis")
            col1, col2 = st.columns([1, 2])
            trend_metric = col1.selectbox("Metric to Track:", metrics, key=f"trend_{i}")
            sel_munis = col2.multiselect("Compare RHUs:", ABRA_MUNIS, default=['Bangued', 'Manabo'], key=f"muni_{i}")
            
            trend_df = tab_data[(tab_data['Metric'] == trend_metric) & (tab_data['Municipality'].isin(sel_munis))]
            trend_df = trend_df.sort_values(by=['Year', 'Period_Order'])
            trend_df['Timeline'] = trend_df['Period'] + " " + trend_df['Year'].astype(str)
            
            if not trend_df.empty:
                fig = px.line(trend_df, x='Timeline', y='Value', color='Municipality', markers=True, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{i}")
            
            # --- DATA TABLE ---
            with st.expander("📄 View Raw Data Table"):
                st.dataframe(tab_data, use_container_width=True)
else:
    st.warning("Please upload your FHSIS files above to populate the Command Center.")
