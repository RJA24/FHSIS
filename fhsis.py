import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="Abra FHSIS Command Center", layout="wide", page_icon="🏥")

PRIORITY_AGENDA = [
    "1. Immunization",
    "2. Nutrition",
    "3. WASH",
    "4. Maternal Health",
    "5. TB & HIV",
    "6. Road Safety",
    "7. NCDs",
    "8. Cancer"
]

# --- ROUTING LOGIC: Assigns files to tabs ---
def get_priority_tab(filename):
    name = filename.lower()
    # 1. Immunization
    if any(x in name for x in ["cpab", "bcg", "dpt", "opv", "ipv", "pcv", "mmr", "fic", "hpv"]): return "1. Immunization"
    # 2. Nutrition
    if any(x in name for x in ["mam", "sam", "vitamin a", "mnp", "lns", "low birth", "bf"]): return "2. Nutrition"
    # 3. WASH
    if any(x in name for x in ["safe water", "sanitation"]): return "3. WASH"
    # 4. Maternal Health
    if any(x in name for x in ["4anc", "8anc", "pospartum", "postpartum"]): return "4. Maternal Health"
    # 5. TB & HIV
    if any(x in name for x in ["tb", "hiv"]): return "5. TB & HIV"
    # 6. Road Safety
    if "traffic" in name: return "6. Road Safety"
    # 7. NCDs
    if any(x in name for x in ["adults risk", "ncd", "hypertensive"]): return "7. NCDs"
    # 8. Cancer
    if any(x in name for x in ["cervical", "breast cancer"]): return "8. Cancer"
    return None

# [Keep your existing parse_fhsis_template and helper functions here]
# ... (Make sure to keep the parse function we refined earlier) ...

# ---------------------------------------------------------
# UI ENGINE
# ---------------------------------------------------------
st.sidebar.title("⚙️ Command Center")
current_year = st.sidebar.selectbox("Assign Year to Uploads:", [2026, 2025, 2024, 2023, 2022, 2021])

st.title("🏥 Abra Provincial FHSIS Command Center")

with st.expander("📂 Upload Templates", expanded=True):
    uploaded_files = st.file_uploader("Upload CSV/Excel", accept_multiple_files=True, type=['csv', 'xlsx'])

if uploaded_files:
    tabs = st.tabs(PRIORITY_AGENDA)
    
    for i, tab_name in enumerate(PRIORITY_AGENDA):
        with tabs[i]:
            st.header(tab_name)
            relevant_files = [f for f in uploaded_files if get_priority_tab(f.name) == tab_name]
            
            if not relevant_files:
                st.info(f"Awaiting data for: {tab_name}")
            else:
                for file in relevant_files:
                    parsed_data, status = parse_fhsis_template(file)
                    if parsed_data is not None:
                        with st.expander(f"📄 {file.name}"):
                            st.dataframe(parsed_data, use_container_width=True)
                    else:
                        st.error(f"Error loading {file.name}")
