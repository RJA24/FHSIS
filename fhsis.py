import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
st.set_page_config(page_title="Abra FHSIS Dashboard", layout="wide", page_icon="🏥")

ABRA_MUNIS = [
    'Bangued', 'Boliney', 'Bucay', 'Bucloc', 'Daguioman', 'Danglas', 
    'Dolores', 'La Paz', 'Lacub', 'Lagangilang', 'Lagayan', 'Langiden', 
    'Licuan-Baay', 'Luba', 'Malibcong', 'Manabo', 'Penarrubia', 'Pidigan', 
    'Pilar', 'Sallapadan', 'San Isidro', 'San Juan', 'San Quintin', 
    'Tayum', 'Tineg', 'Tubo', 'Villaviciosa'
]

PERIOD_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Q1": 4, 
    "Apr": 5, "May": 6, "Jun": 7, "Q2": 8, 
    "Jul": 9, "Aug": 10, "Sep": 11, "Q3": 12, 
    "Oct": 13, "Nov": 14, "Dec": 15, "Q4": 16, "Annual": 17
}

# --- INITIALIZE MASTER DATABASE (Persistent Session Storage) ---
if 'master_db' not in st.session_state:
    st.session_state.master_db = pd.DataFrame(
        columns=['Year', 'Indicator', 'Period', 'Period_Order', 'Municipality', 'Metric', 'Value']
    )

# ---------------------------------------------------------
# THE INTELLIGENT PARSER
# ---------------------------------------------------------
def detect_indicator_type(filename):
    name = filename.lower()
    if "cpab" in name or "bcg" in name: return "Immunization - BCG/HepB"
    if "dpt" in name or "hib" in name: return "Immunization - DPT/HiB/HepB"
    if "opv" in name or "ipv" in name: return "Immunization - Polio"
    if "pcv" in name: return "Immunization - PCV"
    if "mmr" in name or "fic" in name: return "Immunization - MMR/FIC"
    if "hpv" in name: return "Immunization - HPV"
    if "diarrhea" in name: return "Sick Children - Diarrhea"
    if "pneumonia" in name: return "Sick Children - Pneumonia"
    if "mam" in name or "sam" in name: return "Nutrition - Malnutrition"
    if "vitamin a" in name: return "Nutrition - Vitamin A"
    if "mnp" in name: return "Nutrition - MNP"
    if "lns" in name: return "Nutrition - LNS-SQ"
    if "low birth" in name or "bf" in name: return "Nutrition - LBW/BF"
    return "Uncategorized Indicator"

def extract_period(filename):
    match = re.search(r'-\s*([A-Za-z0-9\s]+)\.(csv|xlsx|xls)', filename)
    period = match.group(1).strip() if match else "Annual"
    if period == "Sept": period = "Sep"
    if period == "July": period = "Jul"
    return period

def clean_numeric(val):
    if pd.isna(val): return 0.0
    val = str(val).replace(',', '').replace('%', '').strip()
    try:
        return float(val)
    except:
        return 0.0

@st.cache_data
def parse_fhsis_template(uploaded_file):
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            try:
                df = pd.read_csv(uploaded_file, header=None, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=None, encoding='latin-1')
    except Exception as e:
        return None, f"Could not read file: {e}"

    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)

    area_col_index = None
    for col in df.columns:
        if df[col].astype(str).isin(['Bangued', 'Manabo']).any():
            area_col_index = col
            break
            
    if area_col_index is None: return None, "Could not locate Area column."

    car_start = df[df[area_col_index] == 'C A R'].index.min()
    abra_start = df[df[area_col_index] == 'Abra'].index.min()
    apayao_start = df[df[area_col_index] == 'Apayao'].index.min()

    if pd.isna(car_start): car_start = abra_start - 3
    if pd.isna(abra_start): abra_start = 0
    if pd.isna(apayao_start): apayao_start = len(df)

    header_rows = df.iloc[max(0, car_start-3):car_start].copy()
    header_rows = header_rows.replace(['nan', 'None', '', 'NaN'], pd.NA)
    header_rows = header_rows.ffill(axis=1)

    flat_headers = []
    for col in df.columns:
        col_texts = [str(val) for val in header_rows[col].values if pd.notna(val)]
        clean_texts = []
        for text in col_texts:
            if text not in clean_texts and "Unnamed" not in text:
                clean_texts.append(text)
        header_name = " | ".join(clean_texts)
        if not header_name: header_name = f"Col_{col}"
        flat_headers.append(header_name)
        
    # Deduplicate headers to ensure clean database melting
    seen = {}
    deduped_headers = []
    for h in flat_headers:
        if h in seen:
            seen[h] += 1
            deduped_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            deduped_headers.append(h)
            
    df.columns = deduped_headers

    abra_df = df.iloc[abra_start:apayao_start].copy()
    area_col_name = df.columns[area_col_index]
    clean_df = abra_df[abra_df[area_col_name].isin(ABRA_MUNIS)].copy()
    
    clean_df.rename(columns={area_col_name: 'Municipality'}, inplace=True)
    clean_df.dropna(axis=1, how='all', inplace=True)
    
    final_cols = ['Municipality'] + [col for col in clean_df.columns if 'Total' in col or '%' in col]
    if len(final_cols) == 1: final_cols = clean_df.columns.tolist()

    return clean_df[final_cols], "Success"

# ---------------------------------------------------------
# APP UI & ROUTING
# ---------------------------------------------------------
st.sidebar.title("⚙️ Command Center")
st.sidebar.markdown("### 1. Time Travel Router")
current_year = st.sidebar.selectbox("Assign Year to Uploads:", [2025, 2024, 2023, 2022, 2021])

st.title("🏥 Abra Provincial FHSIS Dashboard")
st.markdown("### Master Database & Executive Summary")

with st.expander(f"📂 Upload {current_year} FHSIS Templates", expanded=True):
    uploaded_files = st.file_uploader(
        "Drag and drop FHSIS CSV or Excel files here", 
        type=['csv', 'xlsx'], 
        accept_multiple_files=True
    )

if uploaded_files:
    with st.spinner("Processing & updating Master Database..."):
        new_records = []
        for file in uploaded_files:
            indicator = detect_indicator_type(file.name)
            period = extract_period(file.name)
            p_order = PERIOD_ORDER.get(period, 99)
            
            parsed_data, status = parse_fhsis_template(file)
            if parsed_data is not None:
                # DATABASE MELTING: Converts wide tables into deep SQL-like records
                metric_cols = [c for c in parsed_data.columns if c != 'Municipality']
                melted = parsed_data.melt(id_vars=['Municipality'], value_vars=metric_cols, var_name='Metric', value_name='Value')
                melted['Value'] = melted['Value'].apply(clean_numeric)
                melted['Year'] = current_year
                melted['Indicator'] = indicator
                melted['Period'] = period
                melted['Period_Order'] = p_order
                new_records.append(melted)

        if new_records:
            new_df = pd.concat(new_records, ignore_index=True)
            
            # UPSERT LOGIC: Replaces old data if you re-upload a corrected file
            combined = pd.concat([st.session_state.master_db, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['Year', 'Indicator', 'Period', 'Municipality', 'Metric'], keep='last')
            st.session_state.master_db = combined
            
            st.success(f"{len(uploaded_files)} files successfully merged into the Master Database.")
        
# ---------------------------------------------------------
# DASHBOARD VISUALIZATION
# ---------------------------------------------------------
db = st.session_state.master_db

if not db.empty:
    st.divider()
    st.sidebar.markdown("### 2. Database Status")
    st.sidebar.success(f"🟢 Active Records: {len(db)}")
    
    if st.sidebar.button("🗑️ Clear Database Memory"):
        st.session_state.master_db = pd.DataFrame(columns=['Year', 'Indicator', 'Period', 'Period_Order', 'Municipality', 'Metric', 'Value'])
        st.rerun()

    indicators = sorted(db['Indicator'].unique())
    tabs = st.tabs(indicators)
    
    for i, ind in enumerate(indicators):
        with tabs[i]:
            ind_df = db[db['Indicator'] == ind]
            metrics = sorted(ind_df['Metric'].unique())
            
            if not metrics:
                st.warning("No metrics found.")
                continue
            
            # --- PHASE 5: EXECUTIVE SUMMARY ---
            st.markdown("### 🏆 Provincial Executive Summary")
            summary_col = st.selectbox("Select Metric for Provincial Report:", metrics, key=f"exec_{ind}_{i}")
            
            metric_df = ind_df[ind_df['Metric'] == summary_col]
            latest_year = metric_df['Year'].max()
            latest_year_df = metric_df[metric_df['Year'] == latest_year]
            latest_period_order = latest_year_df['Period_Order'].max()
            latest_period_df = latest_year_df[latest_year_df['Period_Order'] == latest_period_order]
            latest_period_name = latest_period_df['Period'].iloc[0] if not latest_period_df.empty else "Unknown"
            
            # Auto-calculate the provincial total (averages if it's a percentage)
            provincial_val = latest_period_df['Value'].sum()
            if '%' in summary_col:
                provincial_val = latest_period_df['Value'].mean()
                st.metric(label=f"Provincial Average: {summary_col} ({latest_period_name} {latest_year})", value=f"{provincial_val:.2f}%")
            else:
                st.metric(label=f"Provincial Total: {summary_col} ({latest_period_name} {latest_year})", value=f"{provincial_val:,.0f}")

            st.divider()

            # --- PHASE 4: TREND ANALYSIS ---
            st.markdown("### 📈 Multi-Year Trend Analysis")
            col1, col2 = st.columns([1, 2])
            with col1:
                trend_metric = st.selectbox("Select Metric to Track:", metrics, key=f"trend_{ind}_{i}")
            with col2:
                selected_munis = st.multiselect("Select Municipalities:", options=ABRA_MUNIS, default=['Bangued', 'Manabo'], key=f"muni_{ind}_{i}")
            
            trend_df = ind_df[(ind_df['Metric'] == trend_metric) & (ind_df['Municipality'].isin(selected_munis))]
            trend_df = trend_df.sort_values(by=['Year', 'Period_Order'])
            trend_df['Timeline'] = trend_df['Period'].astype(str) + " " + trend_df['Year'].astype(str)
            
            if not trend_df.empty:
                fig_trend = px.line(
                    trend_df, 
                    x='Timeline', 
                    y='Value', 
                    color='Municipality',
                    markers=True,
                    title=f"Historical Trend: {trend_metric}",
                    template="plotly_white"
                )
                fig_trend.update_traces(line=dict(width=3), marker=dict(size=8))
                st.plotly_chart(fig_trend, use_container_width=True, key=f"chart_trend_{ind}_{i}")
            else:
                st.info("Select municipalities to view trend.")

            st.divider()

            # --- PHASE 3: INDIVIDUAL PERIOD REPORTS ---
            st.markdown("### 📄 Individual RHU Breakdown")
            periods_available = ind_df[['Year', 'Period', 'Period_Order']].drop_duplicates().sort_values(by=['Year', 'Period_Order'], ascending=[False, False])
            
            for _, row in periods_available.iterrows():
                y = row['Year']
                p = row['Period']
                
                with st.expander(f"📊 {p} {y} RHU Data & Chart", expanded=False):
                    bar_metric = st.selectbox(f"Select Metric to Visualize ({p} {y}):", metrics, key=f"bar_{ind}_{y}_{p}_{i}")
                    
                    bar_df = ind_df[(ind_df['Year'] == y) & (ind_df['Period'] == p) & (ind_df['Metric'] == bar_metric)].copy()
                    bar_df = bar_df.sort_values(by='Value', ascending=False)
                    
                    if not bar_df.empty:
                        fig_bar = px.bar(
                            bar_df, 
                            x='Municipality', 
                            y='Value', 
                            title=f"{p} {y}: {bar_metric} by RHU",
                            text_auto='.2s',
                            template="plotly_white",
                            color='Value',
                            color_continuous_scale="Blues"
                        )
                        fig_bar.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                        st.plotly_chart(fig_bar, use_container_width=True, key=f"chart_bar_{ind}_{y}_{p}_{i}")
                        
                        # Pivot table back to wide format for easy reading
                        table_df = ind_df[(ind_df['Year'] == y) & (ind_df['Period'] == p)].pivot(index='Municipality', columns='Metric', values='Value').reset_index()
                        st.dataframe(table_df, use_container_width=True)
else:
    st.info("Awaiting file upload... Drop your FHSIS templates above to build the database.")
