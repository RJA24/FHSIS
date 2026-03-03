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
    # Standardize names for sorting
    if period == "Sept": period = "Sep"
    if period == "July": period = "Jul"
    return period

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
        
    df.columns = flat_headers

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
st.title("🏥 Abra Provincial FHSIS Dashboard")
st.markdown("### Automated Data Pipeline & Trend Analysis (2021-2025)")

with st.expander("📂 Upload FHSIS Templates", expanded=True):
    uploaded_files = st.file_uploader(
        "Drag and drop FHSIS CSV or Excel files here", 
        type=['csv', 'xlsx'], 
        accept_multiple_files=True
    )

if uploaded_files:
    st.success(f"{len(uploaded_files)} files loaded successfully.")
    
    grouped_files = {}
    for file in uploaded_files:
        indicator = detect_indicator_type(file.name)
        if indicator not in grouped_files:
            grouped_files[indicator] = []
        grouped_files[indicator].append(file)
        
    tabs = st.tabs(list(grouped_files.keys()))
    
    for i, (indicator, files) in enumerate(grouped_files.items()):
        with tabs[i]:
            st.markdown(f"## {indicator}")
            
            # 1. PROCESS ALL DATA FOR THIS INDICATOR
            all_period_data = []
            for file in files:
                parsed_data, status = parse_fhsis_template(file)
                if parsed_data is not None:
                    period = extract_period(file.name)
                    parsed_data['Period'] = period
                    parsed_data['Period_Order'] = PERIOD_ORDER.get(period, 99) # For chronological sorting
                    all_period_data.append(parsed_data)
            
            if not all_period_data:
                st.warning("No valid data could be extracted for this indicator.")
                continue
                
            master_df = pd.concat(all_period_data, ignore_index=True)
            numeric_cols = [c for c in master_df.columns if c not in ['Municipality', 'Period', 'Period_Order']]
            
            # 2. THE TREND ANALYSIS ENGINE
            if numeric_cols:
                st.markdown("### 📈 Chronological Trend Analysis")
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    selected_trend_col = st.selectbox(
                        "Select Metric to Track Over Time:", 
                        numeric_cols, 
                        key=f"trend_metric_{indicator}"
                    )
                with col2:
                    selected_munis = st.multiselect(
                        "Select Municipalities to Compare:",
                        options=ABRA_MUNIS,
                        default=['Bangued', 'Manabo'],
                        key=f"trend_munis_{indicator}"
                    )
                
                # Prepare Trend Data
                trend_df = master_df[['Period', 'Period_Order', 'Municipality', selected_trend_col]].copy()
                trend_df[selected_trend_col] = trend_df[selected_trend_col].astype(str).str.replace(',', '').str.replace('%', '')
                trend_df[selected_trend_col] = pd.to_numeric(trend_df[selected_trend_col], errors='coerce').fillna(0)
                
                # Filter by selected municipalities (or show all if none selected)
                if selected_munis:
                    trend_df = trend_df[trend_df['Municipality'].isin(selected_munis)]
                
                # Sort chronologically (Jan -> Feb -> Mar)
                trend_df = trend_df.sort_values(by=['Period_Order', 'Municipality'])
                
                # Plot the Line Chart
                fig_trend = px.line(
                    trend_df, 
                    x='Period', 
                    y=selected_trend_col, 
                    color='Municipality',
                    markers=True,
                    title=f"Trend: {selected_trend_col}",
                    template="plotly_white"
                )
                fig_trend.update_layout(xaxis_title="Reporting Period", yaxis_title="Accomplishment")
                fig_trend.update_traces(line=dict(width=3), marker=dict(size=8))
                st.plotly_chart(fig_trend, use_container_width=True)
                
                st.divider()

            # 3. INDIVIDUAL FILE REPORTS (The Phase 3 Code)
            st.markdown("### 📄 Individual Period Reports")
            for file in files:
                period = extract_period(file.name)
                # Find the specific dataframe for this file from our combined list
                file_df = master_df[master_df['Period'] == period].drop(columns=['Period', 'Period_Order'])
                
                with st.expander(f"📊 {period} Data & Chart", expanded=False):
                    if numeric_cols:
                        selected_bar_col = st.selectbox(
                            f"Select Metric to Visualize ({period}):", 
                            numeric_cols, 
                            key=f"bar_{file.name}"
                        )
                        
                        chart_df = file_df[['Municipality', selected_bar_col]].copy()
                        chart_df[selected_bar_col] = chart_df[selected_bar_col].astype(str).str.replace(',', '').str.replace('%', '')
                        chart_df[selected_bar_col] = pd.to_numeric(chart_df[selected_bar_col], errors='coerce').fillna(0)
                        chart_df = chart_df.sort_values(by=selected_bar_col, ascending=False)
                        
                        fig_bar = px.bar(
                            chart_df, 
                            x='Municipality', 
                            y=selected_bar_col, 
                            title=f"{period}: {selected_bar_col} by RHU",
                            text_auto='.2s',
                            template="plotly_white",
                            color=selected_bar_col,
                            color_continuous_scale="Blues"
                        )
                        fig_bar.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                    st.dataframe(file_df, use_container_width=True)
else:
    st.info("Awaiting file upload... Drop your monthly CSVs above.")
