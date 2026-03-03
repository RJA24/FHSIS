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

PRIORITY_AGENDA = list(AGENDA_TARGETS.keys()) + ["4. Maternal Health", "7. NCDs", "8. Cancer"]

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
# 2. INTELLIGENT ROUTING
# ---------------------------------------------------------
def get_priority_tab(filename):
    name = filename.lower()
    if any(x in name for x in ["cpab", "bcg", "dpt", "opv", "ipv", "pcv", "mmr", "fic", "hpv"]): return "1. Immunization"
    if any(x in name for x in ["mam", "sam", "vitamin a", "stunting", "low birth", "bf"]): return "2. Nutrition"
    if any(x in name for x in ["safe water", "sanitation", "env_"]): return "3. WASH"
    if any(x in name for x in ["4anc", "8anc", "pospartum", "postpartum"]): return "4. Maternal Health"
    if any(x in name for x in ["tb", "hiv"]): return "5. TB & HIV"
    if "traffic" in name: return "6. Road Safety"
    if any(x in name for x in ["adults risk", "ncd", "hypertensive", "seniors"]): return "7. NCDs"
    if any(x in name for x in ["cervical", "breast", "cancer"]): return "8. Cancer"
    return None

# [Existing parse_fhsis_template and cleaning functions remain the same]
# ... (Use your robust parser from previous steps) ...

# ---------------------------------------------------------
# 3. UI ENGINE
# ---------------------------------------------------------
st.sidebar.title("⚙️ Command Center")
target_year = st.sidebar.selectbox("Assign Year to Uploads:", [2026, 2025, 2024, 2023, 2022, 2021], index=1)

if st.sidebar.button("🗑️ Reset Dashboard Memory"):
    st.session_state.master_db = pd.DataFrame(columns=['Year', 'Tab', 'Period', 'Period_Order', 'Municipality', 'Metric', 'Value'])
    st.rerun()

st.title("🏥 Abra Provincial FHSIS Command Center")
st.markdown(f"### Performance Tracking: {target_year}")

with st.expander(f"📂 Upload Data Batch", expanded=False):
    files = st.file_uploader("Upload CSV/Excel", accept_multiple_files=True)

if files:
    # [Upload Logic processing goes here - same as before]
    pass

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
            sum_metric = st.selectbox("Key Metric:", metrics, key=f"sum_{i}")
            
            latest_y = tab_data['Year'].max()
            latest_p_order = tab_data[tab_data['Year'] == latest_y]['Period_Order'].max()
            prov_df = tab_data[(tab_data['Year'] == latest_y) & (tab_data['Period_Order'] == latest_p_order) & (tab_data['Metric'] == sum_metric)]
            
            val = prov_df['Value'].mean() if '%' in sum_metric else prov_df['Value'].sum()
            target = AGENDA_TARGETS.get(tab_name, 0)
            
            # Color logic for performance
            if target > 0:
                delta = val - target
                # For stunting or road deaths, lower is better
                if "Nutrition" in tab_name or "Road Safety" in tab_name:
                    status_color = "normal" if val <= target else "inverse"
                else:
                    status_color = "normal" if val >= target else "inverse"
                st.metric(f"Abra Provincial Performance", f"{val:,.1f}%" if '%' in sum_metric else f"{val:,.0f}", delta=f"Target: {target}%", delta_color=status_color)
            else:
                st.metric(f"Abra Provincial Total", f"{val:,.1f}%" if '%' in sum_metric else f"{val:,.0f}")

            st.divider()
            # [Trend and Table logic goes here]
