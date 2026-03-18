import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import time
import base64
import os
from datetime import datetime
import pytz

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Abra Provincial Health Data Portal", page_icon="Abra_provincial_seal.png", layout="wide")

# --- GLOBAL UI / UX POLISH ---
st.markdown("""
    <style>
    /* 1. Make the header transparent but leave its structure alone (Protects Sidebar Button!) */
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }
    
    /* 2. Adjust padding so the dashboard looks clean */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* 3. DOH Purple active tabs */
    .stTabs [aria-selected="true"] {
        color: #7209b7 !important;
        border-bottom-color: #7209b7 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Conditional CSS applied ONLY to regular users
if not st.session_state.get("is_admin", False):
    st.markdown("""
        <style>
        /* 4. Hide ONLY the top-right toolbar (3-dots & Deploy) */
        [data-testid="stToolbar"] {
            display: none !important;
        }
        
        /* 5. Hide the standard footer */
        footer {
            display: none !important;
        }
        
        /* 6. The Ultimate Badge Assassin */
        /* Targets the exact cloud link and Streamlit's floating UI elements */
        a[href^="https://streamlit.io/cloud"] {
            display: none !important;
        }
        [class*="viewerBadge"] {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

def silent_access_tracker():
    # 1. Check if we have already logged this specific user's session
    if 'has_logged_in' not in st.session_state:
        
        # 2. Basic Bot Filter (Checking if the session is a real browser request)
        # We assume it's human unless the headers explicitly say otherwise.
        is_bot = False
        try:
            user_agent = st.context.headers.get("User-Agent", "").lower()
            bot_keywords = ['bot', 'crawler', 'spider', 'healthcheck', 'uptime']
            if any(bot in user_agent for bot in bot_keywords):
                is_bot = True
        except Exception:
            pass # Fail open and assume human if we can't read headers

        # 3. If it is a human, write to the ACCESS LOG
        if not is_bot:
            try:
                # Set time to Philippine Standard Time (PST)
                pst = pytz.timezone('Asia/Manila')
                now = datetime.now(pst)
                
                current_date = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M:%S")
                
                # Format the new entry
                new_entry = pd.DataFrame([{
                    "Date": current_date,
                    "Time": current_time,
                    "Device": "Human"
                }])
                
                # Connect to GSheets and push the data
                conn = st.connection("gsheets", type=GSheetsConnection)
                
                # Pull existing logs and append the new one
                existing_logs = conn.read(worksheet="ACCESS LOG", ttl=0)
                updated_logs = pd.concat([existing_logs, new_entry], ignore_index=True)
                
                # Push the updated log back to the cloud
                conn.update(worksheet="ACCESS LOG", data=updated_logs)
                
            except Exception as e:
                pass
                
        # 4. Lock the session state so it doesn't log them again if they switch tabs
        st.session_state['has_logged_in'] = True

# Fire the tracker silently in the background
silent_access_tracker()

def apply_custom_css():
    st.markdown("""
        <style>
        /* Adaptive Metric Card Styling */
        [data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border-radius: 8px;
            padding: 15px 20px;
            border: 1px solid rgba(130, 130, 130, 0.2); 
            border-left: 5px solid #1f77b4;
            box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
        }
        
        /* ULTIMATE TEXT WRAPPING */
        [data-testid="stMetricLabel"], 
        [data-testid="stMetricLabel"] > div, 
        [data-testid="stMetricLabel"] p, 
        [data-testid="stMetricLabel"] span {
            white-space: normal !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            text-overflow: unset !important;
            line-height: 1.3 !important;
            height: auto !important;
        }
        
        /* Adaptive text colors */
        [data-testid="stMetricLabel"] p {
            font-size: 0.90rem !important;
            font-weight: 600 !important;
            color: var(--text-color);
        }
        
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] > div {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: var(--text-color);
            white-space: normal !important;
            margin-top: auto !important;
        }
        
        .streamlit-expanderHeader {
            font-weight: 600;
            border-radius: 5px;
            background-color: var(--secondary-background-color);
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_css()

# --- GSHEETS CONFIGURATION ---
IMMUNIZATION_MAPPING = {
    "CPAB_BCG_HepB": "CPAB_Data",
    "Penta": "Penta_Data",
    "Polio": "Polio_Data",
    "PCV": "PCV_Data",
    "MMR": "MMR_Data"
}

NCD_MAPPING = {
    "Adults_Risk": "Adults_NCD_Data",
    "Seniors_Risk": "Seniors_NCD_Data",
    "Cervical_Cancer": "Cervical_Cancer_Data",
    "Breast_Cancer": "Breast_Cancer_Data"
}

WASH_MAPPING = {
    "Safe_Water": "Safe_Water_Data",
    "Sanitation": "Sanitation_Data"
}

MATERNAL_MAPPING = {
    "ANC": "ANC_Data",
    "Nutritional_Status": "Nutritional_Status_Data",
    "Calcium_MMS": "Calcium_MMS_Data",
    "Syphilis_HepB": "Syphilis_HepB_Data",
    "CBC_Gestational": "CBC_Gestational_Data",
    "PPC": "PPC_Data",
    "Livebirths": "Livebirths_Data"
}

MORTALITY_MAPPING = {
    "Premature_NCD": "Premature_NCD_Data",
    "Traffic_Deaths": "Traffic_Deaths_Data",
    "Traffic_Accidents": "Traffic_Accidents_Data"
}

FP_MAPPING = {
    "FP_Beginning": "FP_Beginning_Data",
    "FP_New": "FP_New_Data",
    "FP_Other": "FP_Other_Data",
    "FP_Dropouts": "FP_Dropouts_Data",
    "FP_End": "FP_End_Data",
    "FP_Demand": "FP_Demand_Data"
}

ALL_MAPPINGS = {**IMMUNIZATION_MAPPING, **NCD_MAPPING, **WASH_MAPPING, **MATERNAL_MAPPING, **MORTALITY_MAPPING, **FP_MAPPING}

# --- TARGET WASH INDICATORS ---
TARGET_WASH_COLS = [
    "Projected No. of HHs",
    "HH with Access to Basic Safe Water Supply",
    "HH with Access to Basic Safe Water Supply_Lvl_1",
    "HH with Access to Basic Safe Water Supply_Lvl_2",
    "HH with Access to Basic Safe Water Supply_Lvl_3",
    "HHs using Safely Managed Drinking-water Services",
    "HH with Basic Sanitation Facility",
    "Pour / flush Toilet connected to Septic Tank",
    "Pour / flush Toilet connected to Community sewer/sewerage system",
    "Pour / flush Toilet connected to Ventillated improved Pit Latrine (VIP)",
    "HHs using Safely Managed Sanitation Service"
]

# --- GSHEETS FUNCTIONS (OPTIMIZED FOR API LIMITS) ---
def save_data_to_gsheets(new_data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    for app_key, new_df in new_data_dict.items():
        sheet_name = ALL_MAPPINGS[app_key]
        combined_df = new_df.copy()
        
        with st.spinner(f"Merging and saving {app_key} to cloud database..."):
            try:
                try:
                    existing_df = conn.read(worksheet=sheet_name, ttl=0)
                    if not existing_df.empty and 'Area' in existing_df.columns:
                        existing_df = existing_df.dropna(subset=['Area', 'Year'])
                    else:
                        existing_df = pd.DataFrame()
                except Exception:
                    existing_df = pd.DataFrame() 
                
                if not existing_df.empty:
                    old_df = existing_df.copy()
                    old_df['Year_Num'] = pd.to_numeric(old_df['Year'], errors='coerce').fillna(0).astype(int)
                    new_df['Year_Num'] = pd.to_numeric(new_df['Year'], errors='coerce').fillna(0).astype(int)
                    
                    upload_years = new_df['Year_Num'].unique()
                    old_df = old_df[~old_df['Year_Num'].isin(upload_years)]
                    
                    old_df = old_df.drop(columns=['Year_Num'])
                    new_df_clean = new_df.drop(columns=['Year_Num'])
                    
                    combined_df = pd.concat([old_df, new_df_clean], ignore_index=True)
                    
                combined_df.columns = combined_df.columns.astype(str)
                combined_df = combined_df.fillna("")
                    
                old_len = len(existing_df)
                new_len = len(combined_df)
                
                if new_len < old_len:
                    diff = old_len - new_len
                    padding = pd.DataFrame([[""] * len(combined_df.columns)] * diff, columns=combined_df.columns)
                    write_df = pd.concat([combined_df, padding], ignore_index=True)
                    write_df = write_df.fillna("")
                    conn.update(worksheet=sheet_name, data=write_df)
                else:
                    conn.update(worksheet=sheet_name, data=combined_df)
                
                st.session_state['fhsis_data'][app_key] = combined_df
                time.sleep(4) 
                
            except Exception as e:
                st.error(f"❌ Failed to save {sheet_name}. API Error: {e}")
                
    st.cache_data.clear()

# THIS IS THE MAGIC SPEED UP FIX RIGHT HERE
@st.cache_data(ttl=3600)
def load_data_from_gsheets():
    loaded_data = {}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        for app_key, sheet_name in ALL_MAPPINGS.items():
            try:
                df = conn.read(worksheet=sheet_name, ttl="10m") 
                if not df.empty and 'Area' in df.columns:
                    df = df.dropna(subset=['Area', 'Year'])
                    loaded_data[app_key] = df
            except Exception:
                pass 
            time.sleep(0.5)
    except Exception as e:
        st.error("Google Sheets connection not fully configured yet.")
    return loaded_data

def nuke_cloud_database(selected_keys):
    conn = st.connection("gsheets", type=GSheetsConnection)
    existing_data = load_data_from_gsheets()
    
    for app_key in selected_keys:
        sheet_name = ALL_MAPPINGS[app_key]
        with st.spinner(f"Nuking {sheet_name}..."):
            try:
                if app_key in existing_data and not existing_data[app_key].empty:
                    old_len = len(existing_data[app_key])
                    cols = existing_data[app_key].columns
                    blank_df = pd.DataFrame([[""] * len(cols)] * (old_len + 5), columns=cols)
                    conn.update(worksheet=sheet_name, data=blank_df)
                    time.sleep(2.5) 
                    
                empty_df = pd.DataFrame(columns=['Area', 'Month', 'Year']) 
                conn.update(worksheet=sheet_name, data=empty_df)
                time.sleep(2.5) 
                
                if app_key in st.session_state.get('fhsis_data', {}):
                    del st.session_state['fhsis_data'][app_key]
                    
            except Exception as e:
                st.warning(f"⚠️ Skipped {sheet_name} (Tab might not exist yet or API limit reached).")
            
    st.cache_data.clear()

def clear_session_data():
    st.session_state['fhsis_data'] = {}

# --- LIST OF 27 ABRA RHUs & COORDINATES ---
ABRA_RHUS = [
    "Bangued", "Boliney", "Bucay", "Bucloc", "Daguioman", "Danglas", 
    "Dolores", "La Paz", "Lacub", "Lagangilang", "Lagayan", "Langiden", 
    "Licuan-Baay", "Luba", "Malibcong", "Manabo", "Penarrubia", "Pidigan", 
    "Pilar", "Sallapadan", "San Isidro", "San Juan", "San Quintin", 
    "Tayum", "Tineg", "Tubo", "Villaviciosa"
]

ABRA_COORDS = {
    "Bangued": (17.595, 120.613), "Boliney": (17.394, 120.814), "Bucay": (17.541, 120.720),
    "Bucloc": (17.433, 120.783), "Daguioman": (17.448, 120.822), "Danglas": (17.728, 120.655),
    "Dolores": (17.647, 120.710), "La Paz": (17.668, 120.672), "Lacub": (17.669, 120.945),
    "Lagangilang": (17.618, 120.735), "Lagayan": (17.734, 120.730), "Langiden": (17.579, 120.575),
    "Licuan-Baay": (17.585, 120.884), "Luba": (17.324, 120.698), "Malibcong": (17.564, 120.988),
    "Manabo": (17.434, 120.702), "Penarrubia": (17.563, 120.648), "Pidigan": (17.572, 120.589),
    "Pilar": (17.421, 120.595), "Sallapadan": (17.456, 120.763), "San Isidro": (17.468, 120.606),
    "San Juan": (17.683, 120.738), "San Quintin": (17.544, 120.521), "Tayum": (17.617, 120.665),
    "Tineg": (17.785, 120.938), "Tubo": (17.234, 120.748), "Villaviciosa": (17.439, 120.632)
}

# --- DATA CLEANERS ---
@st.cache_data
def load_and_clean_fhsis_data(uploaded_file, year):
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            sheets_to_process = {"Jan": df_raw} 
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            invalid_keywords = ["summary", "cons", "ytd", "annual", "quarter", "sem"]
            month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                         "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
            
            for sheet in xls.sheet_names:
                sheet_lower = sheet.lower().strip()
                months_found = [m for m in valid_months if m in sheet_lower]
                if len(months_found) != 1: continue
                if any(inv in sheet_lower for inv in invalid_keywords): continue
                sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            for idx, row in df.iterrows():
                if any('Area' in str(val).strip() for val in row.values if pd.notna(val)):
                    area_row_idx = idx; break
            if area_row_idx == -1: continue 
            sub_row_idx = -1
            for idx in range(area_row_idx + 1, min(area_row_idx + 5, len(df))):
                row = df.iloc[idx]
                if any(str(val).strip() in ['Male', 'Female'] for val in row.values if pd.notna(val)):
                    sub_row_idx = idx; break

            main_headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], np.nan, regex=True).ffill()
            sub_headers = df.iloc[sub_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True) if sub_row_idx != -1 else pd.Series([''] * len(main_headers))

            flat_cols = []
            for top, bot in zip(main_headers, sub_headers):
                top_str = str(top).strip().replace('\n', ' ') if pd.notna(top) and str(top) != 'nan' else ""
                bot_str = str(bot).strip().replace('\n', ' ') if bot and str(bot) != 'nan' else ""
                if bot_str and bot_str not in top_str and top_str: flat_cols.append(f"{top_str}_{bot_str}")
                elif top_str: flat_cols.append(top_str)
                else: flat_cols.append(bot_str)

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
                if 'Area' in df_clean.columns: df_clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                df_clean.rename(columns={first_col: 'Area'}, inplace=True)
            
            df_clean.dropna(subset=['Area'], inplace=True)
            df_clean['Area_Clean'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area_Clean'].isin(ABRA_RHUS)]
            df_clean['Area'] = df_clean['Area_Clean']
            df_clean.drop(columns=['Area_Clean'], inplace=True)
            df_clean['Month'] = month_val
            df_clean['Year'] = year
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Year', 'Interpretation', 'Recommendation/Actions Taken']:
                    if isinstance(df_clean[col], pd.DataFrame):
                        df_clean[col] = pd.to_numeric(df_clean[col].iloc[:, 0], errors='coerce').fillna(0)
                    else:
                        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
            all_months_data.append(df_clean)
        
        if not all_months_data: raise ValueError("Could not find properly formatted monthly sheets in the file.")
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return None

@st.cache_data
def load_and_clean_ncd_data(uploaded_file, year):
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheets_to_process = {}
        valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        invalid_keywords = ["summary", "cons", "ytd", "annual", "quarter", "sem"]
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                     "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
        
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower().strip()
            months_found = [m for m in valid_months if m in sheet_lower]
            if len(months_found) != 1: continue
            if any(inv in sheet_lower for inv in invalid_keywords): continue
            sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            data_start_idx = -1
            
            for idx, row in df.iterrows():
                row_str = [str(val).strip().upper() for val in row.values if pd.notna(val)]
                if any('AREA' in v for v in row_str) and area_row_idx == -1:
                    area_row_idx = idx
                if area_row_idx != -1 and idx > area_row_idx:
                    if any(v in ['C A R', 'CAR', 'ABRA', 'BANGUED'] for v in row_str):
                        data_start_idx = idx
                        break
                        
            if area_row_idx == -1 or data_start_idx == -1: continue
            
            headers_df = df.iloc[area_row_idx:data_start_idx].copy()
            headers_df.iloc[0] = headers_df.iloc[0].ffill() 
            if len(headers_df) > 1: headers_df.iloc[1] = headers_df.iloc[1].ffill() 
            
            flat_cols = []
            for col_idx in range(headers_df.shape[1]):
                parts = []
                for row_idx in range(headers_df.shape[0]):
                    val = str(headers_df.iloc[row_idx, col_idx]).strip().replace('\n', ' ')
                    if val and val != 'nan' and "Unnamed:" not in val:
                        if not parts or val != parts[-1]:
                            parts.append(val)
                col_name = "_".join(parts)
                if not col_name: col_name = f"Empty_{col_idx}"
                flat_cols.append(col_name)
                
            seen = set()
            unique_cols = []
            for c in flat_cols:
                new_c = c
                counter = 1
                while new_c in seen:
                    new_c = f"{c}_{counter}"
                    counter += 1
                seen.add(new_c)
                unique_cols.append(new_c)

            clean = df.iloc[data_start_idx:].copy()
            clean.columns = unique_cols
            
            area_col = [c for c in unique_cols if "AREA" in c.upper()][0]
            if area_col != 'Area':
                if 'Area' in clean.columns: clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                clean.rename(columns={area_col: 'Area'}, inplace=True)
            
            clean.dropna(subset=['Area'], inplace=True)
            clean['Area_Clean'] = clean['Area'].astype(str).str.strip()
            clean = clean[clean['Area_Clean'].isin(ABRA_RHUS)]
            clean['Area'] = clean['Area_Clean']
            clean.drop(columns=['Area_Clean'], inplace=True)
            clean['Month'] = month_val
            clean['Year'] = year
            
            for col in clean.columns:
                if col not in ['Area', 'Month', 'Year', 'Interpretation', 'Recommendation/Actions Taken']:
                    clean[col] = pd.to_numeric(clean[col], errors='coerce').fillna(0)
            all_months_data.append(clean)
            
        if not all_months_data: raise ValueError("Could not find properly formatted monthly sheets.")
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"NCD Template Error processing {uploaded_file.name}: {e}")
        return None

@st.cache_data
def load_and_clean_wash_data(uploaded_file, year):
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            q_val = "Q1"
            name_low = uploaded_file.name.lower()
            if "q2" in name_low or "qtr2" in name_low: q_val = "Q2"
            elif "q3" in name_low or "qtr3" in name_low: q_val = "Q3"
            elif "q4" in name_low or "qtr4" in name_low: q_val = "Q4"
            sheets_to_process = {q_val: df_raw}
        else:
            xls = pd.ExcelFile(uploaded_file)
            sheets_to_process = {}
            valid_qs = ["qtr1", "q1", "qtr2", "q2", "qtr3", "q3", "qtr4", "q4"]
            q_map = {"qtr1": "Q1", "q1": "Q1", "qtr2": "Q2", "q2": "Q2", 
                     "qtr3": "Q3", "q3": "Q3", "qtr4": "Q4", "q4": "Q4"}
            
            for sheet in xls.sheet_names:
                sheet_lower = sheet.lower().strip()
                for q_key in valid_qs:
                    if q_key in sheet_lower:
                        sheets_to_process[q_map[q_key]] = pd.read_excel(xls, sheet_name=sheet, header=None)
                        break

        all_q_data = []
        for q_val, df in sheets_to_process.items():
            area_row_idx = -1
            data_start_idx = -1
            
            for idx, row in df.iterrows():
                row_vals = [str(val).upper() for val in row.values if pd.notna(val)]
                
                if area_row_idx == -1 and any(k in v for v in row_vals for k in ['AREA', 'MUNICIPALITY', 'CITY']):
                    area_row_idx = idx
                    
                if area_row_idx != -1 and idx > area_row_idx:
                    if any(v in ['C A R', 'CAR', 'ABRA', 'BANGUED'] for v in row_vals):
                        data_start_idx = idx
                        break
                        
            if area_row_idx == -1 or data_start_idx == -1: 
                continue
            
            headers_df = df.iloc[area_row_idx:data_start_idx].copy()
            for i in range(len(headers_df)):
                headers_df.iloc[i] = headers_df.iloc[i].ffill() 
            
            flat_cols = []
            for col_idx in range(headers_df.shape[1]):
                parts = []
                for row_idx in range(headers_df.shape[0]):
                    val = str(headers_df.iloc[row_idx, col_idx]).strip().replace('\n', ' ')
                    if val and val != 'nan' and "Unnamed:" not in val:
                        if not parts or val != parts[-1]:
                            parts.append(val)
                col_name = "_".join(parts)
                if not col_name: col_name = f"Empty_{col_idx}"
                flat_cols.append(col_name)
                
            seen = set()
            unique_cols = []
            for c in flat_cols:
                new_c = c
                counter = 1
                while new_c in seen:
                    new_c = f"{c}_{counter}"
                    counter += 1
                seen.add(new_c)
                unique_cols.append(new_c)

            clean = df.iloc[data_start_idx:].copy()
            clean.columns = unique_cols
            
            area_col = next((c for c in unique_cols if any(k in c.upper() for k in ['AREA', 'MUNICIPALITY', 'CITY'])), unique_cols[0])
            
            if area_col != 'Area':
                if 'Area' in clean.columns: clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                clean.rename(columns={area_col: 'Area'}, inplace=True)

            renamed_cols = {}
            found_targets = set()
            
            for c in clean.columns:
                c_upper = c.upper()
                target = None
                
                if "PROJECTED" in c_upper and "HH" in c_upper:
                    target = "Projected No. of HHs"
                elif "SAFELY MANAGED DRINKING" in c_upper and "%" not in c_upper:
                    target = "HHs using Safely Managed Drinking-water Services"
                elif "SAFELY MANAGED SANITATION" in c_upper and "%" not in c_upper:
                    target = "HHs using Safely Managed Sanitation Service"
                elif "LEVEL 1" in c_upper and "%" not in c_upper:
                    target = "HH with Access to Basic Safe Water Supply_Lvl_1"
                elif "LEVEL 2" in c_upper and "%" not in c_upper:
                    target = "HH with Access to Basic Safe Water Supply_Lvl_2"
                elif "LEVEL 3" in c_upper and "%" not in c_upper:
                    target = "HH with Access to Basic Safe Water Supply_Lvl_3"
                elif "SEPTIC TANK" in c_upper and "%" not in c_upper:
                    target = "Pour / flush Toilet connected to Septic Tank"
                elif "COMMUNITY SEWER" in c_upper and "%" not in c_upper:
                    target = "Pour / flush Toilet connected to Community sewer/sewerage system"
                elif "PIT LATRINE" in c_upper and "%" not in c_upper:
                    target = "Pour / flush Toilet connected to Ventillated improved Pit Latrine (VIP)"
                elif "BASIC SAFE WATER" in c_upper and "TOTAL" in c_upper and "%" not in c_upper:
                    target = "HH with Access to Basic Safe Water Supply"
                elif "BASIC SANITATION" in c_upper and "TOTAL" in c_upper and "%" not in c_upper:
                    target = "HH with Basic Sanitation Facility"

                if target and target not in found_targets:
                    renamed_cols[c] = target
                    found_targets.add(target)

            clean.rename(columns=renamed_cols, inplace=True)
            
            keep_cols = ['Area'] + list(found_targets)
            clean = clean.loc[:, ~clean.columns.duplicated()]
            clean = clean[[c for c in keep_cols if c in clean.columns]]
            
            clean.dropna(subset=['Area'], inplace=True)
            clean['Area_Clean'] = clean['Area'].astype(str).str.strip()
            clean = clean[clean['Area_Clean'].isin(ABRA_RHUS)]
            clean['Area'] = clean['Area_Clean']
            clean.drop(columns=['Area_Clean'], inplace=True)
            clean['Month'] = q_val  
            clean['Year'] = year
            
            for col in clean.columns:
                if col not in ['Area', 'Month', 'Year']:
                    clean[col] = pd.to_numeric(clean[col], errors='coerce').fillna(0)
                    
            if all(c in clean.columns for c in ["HH with Access to Basic Safe Water Supply_Lvl_1", "HH with Access to Basic Safe Water Supply_Lvl_2", "HH with Access to Basic Safe Water Supply_Lvl_3"]):
                clean["HH with Access to Basic Safe Water Supply"] = clean["HH with Access to Basic Safe Water Supply_Lvl_1"] + clean["HH with Access to Basic Safe Water Supply_Lvl_2"] + clean["HH with Access to Basic Safe Water Supply_Lvl_3"]
                
            if all(c in clean.columns for c in ["Pour / flush Toilet connected to Septic Tank", "Pour / flush Toilet connected to Community sewer/sewerage system", "Pour / flush Toilet connected to Ventillated improved Pit Latrine (VIP)"]):
                clean["HH with Basic Sanitation Facility"] = clean["Pour / flush Toilet connected to Septic Tank"] + clean["Pour / flush Toilet connected to Community sewer/sewerage system"] + clean["Pour / flush Toilet connected to Ventillated improved Pit Latrine (VIP)"]

            all_q_data.append(clean)
            
        if not all_q_data: 
            st.error(f"Could not locate correct Municipality headers in {uploaded_file.name}.")
            return None
            
        return pd.concat(all_q_data, ignore_index=True)
    except Exception as e:
        st.error(f"WASH Template Parsing Error processing {uploaded_file.name}: {e}")
        return None

@st.cache_data
def load_and_clean_maternal_data(uploaded_file, year, template_type="ANC"):
    try:
        sheets_to_process = {}
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                     "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
                     
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            name_low = uploaded_file.name.lower()
            valid_months = list(month_map.keys())
            month_found = "Jan" 
            for m in valid_months:
                if m in name_low:
                    month_found = month_map[m]
                    break
            sheets_to_process = {month_found: df_raw}
        else:
            xls = pd.ExcelFile(uploaded_file)
            valid_months = list(month_map.keys())
            invalid_keywords = ["summary", "cons", "ytd", "annual", "quarter", "sem", "elig", "q1", "q2", "q3", "q4"]
            
            for sheet in xls.sheet_names:
                sheet_lower = sheet.lower().strip()
                months_found = [m for m in valid_months if m in sheet_lower]
                if len(months_found) != 1: continue
                if any(inv in sheet_lower for inv in invalid_keywords): continue
                sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            data_start_idx = -1
            
            for idx, row in df.iterrows():
                row_str = [str(val).strip().upper() for val in row.values if pd.notna(val)]
                if any('AREA' in v for v in row_str) and area_row_idx == -1:
                    area_row_idx = idx
                if area_row_idx != -1 and idx > area_row_idx:
                    if any(v in ['C A R', 'CAR', 'ABRA', 'BANGUED'] for v in row_str):
                        data_start_idx = idx
                        break
                        
            if area_row_idx == -1 or data_start_idx == -1: continue
            
            clean = df.iloc[data_start_idx:].copy()
            
            if template_type == "Livebirths":
                lb_clean = pd.DataFrame()
                lb_clean['Area_Original'] = clean.iloc[:, 0]
                lb_clean['Area_Clean'] = lb_clean['Area_Original'].astype(str).str.strip()
                lb_clean = lb_clean[lb_clean['Area_Clean'].isin(ABRA_RHUS)]
                lb_clean['Area'] = lb_clean['Area_Clean']
                lb_clean.drop(columns=['Area_Clean', 'Area_Original'], inplace=True)
                
                valid_indices = lb_clean.index
                clean_filtered = clean.loc[valid_indices]
                
                lb_clean['Month'] = month_val
                lb_clean['Year'] = year
                lb_clean['Total Livebirths_Total'] = pd.to_numeric(clean_filtered.iloc[:, 1], errors='coerce').fillna(0)
                
                if clean_filtered.shape[1] > 129:
                    lb_clean['Total Deliveries_10-14'] = pd.to_numeric(clean_filtered.iloc[:, 127], errors='coerce').fillna(0)
                    lb_clean['Total Deliveries_15-19'] = pd.to_numeric(clean_filtered.iloc[:, 128], errors='coerce').fillna(0)
                    lb_clean['Total Deliveries_20-49'] = pd.to_numeric(clean_filtered.iloc[:, 129], errors='coerce').fillna(0)
                    lb_clean['Total Deliveries_Total'] = lb_clean['Total Deliveries_10-14'] + lb_clean['Total Deliveries_15-19'] + lb_clean['Total Deliveries_20-49']
                    
                all_months_data.append(lb_clean)
                continue
                
            headers_df = df.iloc[area_row_idx:data_start_idx].copy()
            for i in range(len(headers_df)):
                headers_df.iloc[i] = headers_df.iloc[i].ffill() 
            
            flat_cols = []
            for col_idx in range(headers_df.shape[1]):
                parts = []
                for row_idx in range(headers_df.shape[0]):
                    val = str(headers_df.iloc[row_idx, col_idx]).strip().replace('\n', ' ')
                    if val and val != 'nan' and "Unnamed:" not in val:
                        if not parts or val != parts[-1]:
                            parts.append(val)
                col_name = "_".join(parts)
                if not col_name: col_name = f"Empty_{col_idx}"
                flat_cols.append(col_name)
                
            seen = set()
            unique_cols = []
            for c in flat_cols:
                new_c = c
                counter = 1
                while new_c in seen:
                    new_c = f"{c}_{counter}"
                    counter += 1
                seen.add(new_c)
                unique_cols.append(new_c)

            clean.columns = unique_cols
            
            area_col = next((c for c in unique_cols if "AREA" in c.upper()), unique_cols[0])
            if area_col != 'Area':
                if 'Area' in clean.columns: clean.rename(columns={'Area': 'Area_Original'}, inplace=True)
                clean.rename(columns={area_col: 'Area'}, inplace=True)
            
            clean.dropna(subset=['Area'], inplace=True)
            clean['Area_Clean'] = clean['Area'].astype(str).str.strip()
            clean = clean[clean['Area_Clean'].isin(ABRA_RHUS)]
            clean['Area'] = clean['Area_Clean']
            clean.drop(columns=['Area_Clean'], inplace=True)
            clean['Month'] = month_val
            clean['Year'] = year
            
            cols_to_drop = [c for c in clean.columns if "total deliveries" in str(c).lower() or "total livebirths" in str(c).lower()]
            clean.drop(columns=[c for c in cols_to_drop if c in clean.columns], inplace=True)
            
            base_indicators = [c.replace("_10-14", "") for c in clean.columns if c.endswith("_10-14")]
            for base in base_indicators:
                c14 = f"{base}_10-14"
                c19 = f"{base}_15-19"
                c49 = f"{base}_20-49"
                cTotal = f"{base}_Total"
                if c14 in clean.columns and c19 in clean.columns and c49 in clean.columns:
                    clean[c14] = pd.to_numeric(clean[c14], errors='coerce').fillna(0)
                    clean[c19] = pd.to_numeric(clean[c19], errors='coerce').fillna(0)
                    clean[c49] = pd.to_numeric(clean[c49], errors='coerce').fillna(0)
                    clean[cTotal] = clean[c14] + clean[c19] + clean[c49]
            
            for col in clean.columns:
                if col not in ['Area', 'Month', 'Year', 'Interpretation', 'Recommendation/Actions Taken']:
                    clean[col] = pd.to_numeric(clean[col], errors='coerce').fillna(0)
            all_months_data.append(clean)
            
        if not all_months_data: raise ValueError("Could not find properly formatted monthly sheets.")
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"Maternal Template Parsing Error for {uploaded_file.name}: {e}")
        return None

# --- ADDED CACHE HERE ---
@st.cache_data
def load_and_clean_mortality_data(uploaded_file, year):
    try:
        name_low = uploaded_file.name.lower()
        is_premature_ncd = "plus 1" in name_low or "premature" in name_low
        is_traffic_death = "plus 2" in name_low or "traffic injuries" in name_low or "traffic death" in name_low
        is_traffic_acc = "plus 3" in name_low or "traffic accident" in name_low
        
        valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "q1", "q2", "q3", "q4", "2025"]
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                     "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec",
                     "q1": "Q1", "q2": "Q2", "q3": "Q3", "q4": "Q4", "2025": "Annual"}

        sheets_to_process = {}
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
            month_found = "Jan" 
            for m in valid_months:
                if m in name_low:
                    month_found = month_map[m]
                    break
            sheets_to_process = {month_found: df_raw}
        else:
            xls = pd.ExcelFile(uploaded_file)
            for sheet in xls.sheet_names:
                sheet_lower = sheet.lower().strip()
                months_found = [m for m in valid_months if m in sheet_lower]
                if len(months_found) != 1: continue
                sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []

        for month_val, df in sheets_to_process.items():
            df = df.dropna(how='all').reset_index(drop=True)
            
            if not (is_premature_ncd or is_traffic_death or is_traffic_acc):
                head_str = str(df.head(15).values).lower()
                if "cardiovascular" in head_str or "cancer" in head_str: is_premature_ncd = True
                elif "due to traffic injuries" in head_str: is_traffic_death = True
                elif "road accidents" in head_str: is_traffic_acc = True
            
            area_col_idx = -1
            for r_idx, row in df.iterrows():
                for c_idx, val in enumerate(row):
                    if pd.notna(val) and "BANGUED" in str(val).upper():
                        area_col_idx = c_idx
                        break
                if area_col_idx != -1:
                    break
                    
            if area_col_idx == -1:
                continue 
            
            if is_premature_ncd:
                offsets = [1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 18, 19, 20]
                col_names = [
                    'Elig. Pop.',
                    'Total Premature Deaths_Male', 'Total Premature Deaths_Female', 'Total Premature Deaths_Total',
                    'CVD Deaths_Male', 'CVD Deaths_Female', 'CVD Deaths_Total',
                    'Cancer Deaths_Male', 'Cancer Deaths_Female', 'Cancer Deaths_Total',
                    'Diabetes Deaths_Male', 'Diabetes Deaths_Female', 'Diabetes Deaths_Total',
                    'Respiratory Disease Deaths_Male', 'Respiratory Disease Deaths_Female', 'Respiratory Disease Deaths_Total'
                ]
            elif is_traffic_death:
                offsets = [1, 2, 3, 4]
                col_names = ['Elig. Pop.', 'Traffic Injury Deaths_Male', 'Traffic Injury Deaths_Female', 'Traffic Injury Deaths_Total']
            elif is_traffic_acc:
                offsets = [1]
                col_names = ['Total Road Accidents_Total'] 
            else:
                continue 
                
            def extract_rhu(area_val):
                area_up = str(area_val).upper()
                for rhu in ABRA_RHUS:
                    if rhu.upper() in area_up:
                        return rhu
                return None
                
            mapped_df = pd.DataFrame()
            mapped_df['Matched_RHU'] = df[area_col_idx].apply(extract_rhu)
            mapped_df['Area'] = mapped_df['Matched_RHU']
            
            for i, offset in enumerate(offsets):
                target_idx = area_col_idx + offset
                if target_idx < df.shape[1]:
                    mapped_df[col_names[i]] = pd.to_numeric(df[target_idx], errors='coerce').fillna(0)
                else:
                    mapped_df[col_names[i]] = 0
                    
            mapped_df = mapped_df.dropna(subset=['Area'])
            mapped_df = mapped_df.drop(columns=['Matched_RHU'])
            mapped_df['Month'] = month_val
            mapped_df['Year'] = year
            
            all_months_data.append(mapped_df)
            
        if not all_months_data: raise ValueError("Could not locate RHU data in the file.")
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        import traceback
        st.error(f"Mortality Template Error processing {uploaded_file.name}: {e}")
        st.code(traceback.format_exc())
        return None

# --- FAMILY PLANNING DATA CLEANERS ---
@st.cache_data
def load_and_clean_fp_methods(uploaded_file, year):
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheets_to_process = {}
        valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        invalid_keywords = ["summary", "cons", "ytd", "annual", "quarter", "sem", "q1", "q2", "q3", "q4"]
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                     "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
        
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower().strip()
            months_found = [m for m in valid_months if m in sheet_lower]
            if len(months_found) != 1: continue
            if any(inv in sheet_lower for inv in invalid_keywords): continue
            sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            sub_row_idx = -1
            
            # Find the header row (contains 'Area' and Method Names)
            for idx, row in df.iterrows():
                row_str = [str(val).strip().upper() for val in row.values if pd.notna(val)]
                if any('AREA' in v for v in row_str):
                    area_row_idx = idx
                    break
            
            if area_row_idx == -1: continue
            
            # Find the sub-header row (contains age groups 10-14, 15-19, 20-49)
            for idx in range(area_row_idx + 1, min(area_row_idx + 4, len(df))):
                row_str = [str(val).strip() for val in df.iloc[idx].values if pd.notna(val)]
                if any('10-14' in v or '15-19' in v for v in row_str):
                    sub_row_idx = idx
                    break
                    
            if sub_row_idx == -1: continue

            main_headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], np.nan, regex=True).ffill()
            sub_headers = df.iloc[sub_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True)

            flat_cols = []
            for top, bot in zip(main_headers, sub_headers):
                top_str = str(top).strip().replace('\n', ' ') if pd.notna(top) and str(top) != 'nan' else ""
                bot_str = str(bot).strip().replace('\n', ' ') if bot and str(bot) != 'nan' else ""
                
                # Combine Method + Age Group (e.g., "Condom_15-19")
                if bot_str and bot_str not in top_str and top_str: 
                    flat_cols.append(f"{top_str}_{bot_str}")
                elif top_str: 
                    flat_cols.append(top_str)
                else: 
                    flat_cols.append(bot_str)

            # Ensure unique columns
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

            df_clean = df.iloc[sub_row_idx + 1:].copy()
            df_clean.columns = unique_cols
            df_clean = df_clean.loc[:, df_clean.columns != '']

            area_col = next((c for c in df_clean.columns if 'AREA' in c.upper()), df_clean.columns[0])
            if area_col != 'Area':
                df_clean.rename(columns={area_col: 'Area'}, inplace=True)
            
            df_clean.dropna(subset=['Area'], inplace=True)
            df_clean['Area_Clean'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area_Clean'].isin(ABRA_RHUS)]
            df_clean['Area'] = df_clean['Area_Clean']
            df_clean.drop(columns=['Area_Clean'], inplace=True)
            df_clean['Month'] = month_val
            df_clean['Year'] = year
            
            # Clean numeric columns
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Year']:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
                    
            all_months_data.append(df_clean)
            
        if not all_months_data: raise ValueError("Could not find properly formatted monthly sheets.")
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"Family Planning Error processing {uploaded_file.name}: {e}")
        return None

@st.cache_data
def load_and_clean_fp_demand(uploaded_file, year):
    # Specialized cleaner just for the "Demand Satisfied" template
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheets_to_process = {}
        valid_months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        month_map = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", 
                     "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
        
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower().strip()
            months_found = [m for m in valid_months if m in sheet_lower and "summary" not in sheet_lower]
            if len(months_found) == 1:
                sheets_to_process[month_map[months_found[0]]] = pd.read_excel(xls, sheet_name=sheet, header=None)

        all_months_data = []
        for month_val, df in sheets_to_process.items():
            area_row_idx = -1
            for idx, row in df.iterrows():
                row_str = [str(val).strip().upper() for val in row.values if pd.notna(val)]
                if any('AREA' in v for v in row_str) and any('DEMAND' in v for v in row_str):
                    area_row_idx = idx
                    break
            
            if area_row_idx == -1: continue
            
            headers = df.iloc[area_row_idx].astype(str).replace([r'^Unnamed:.*', r'^\s*$', r'^nan$'], '', regex=True)
            df_clean = df.iloc[area_row_idx + 1:].copy()
            df_clean.columns = headers
            df_clean = df_clean.loc[:, df_clean.columns != '']
            
            area_col = next((c for c in df_clean.columns if 'AREA' in c.upper()), df_clean.columns[0])
            df_clean.rename(columns={area_col: 'Area'}, inplace=True)
            
            df_clean.dropna(subset=['Area'], inplace=True)
            df_clean['Area_Clean'] = df_clean['Area'].astype(str).str.strip()
            df_clean = df_clean[df_clean['Area_Clean'].isin(ABRA_RHUS)]
            df_clean['Area'] = df_clean['Area_Clean']
            
            keep_cols = ['Area'] + [c for c in df_clean.columns if c != 'Area' and c != 'Area_Clean']
            df_clean = df_clean[keep_cols]
            df_clean['Month'] = month_val
            df_clean['Year'] = year
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Year']:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
            all_months_data.append(df_clean)
            
        return pd.concat(all_months_data, ignore_index=True)
    except Exception as e:
        st.error(f"Demand Satisfied Error processing {uploaded_file.name}: {e}")
        return None

# --- INITIALIZE CLOUD DATA ---
# This spinner will only show up when the cache is empty (like the first load of the day)
if 'fhsis_data' not in st.session_state:
    with st.spinner("🔄 Syncing latest DOH metrics from the cloud..."):
        st.session_state['fhsis_data'] = load_data_from_gsheets()

# --- SIDEBAR & RBAC ---
with st.sidebar:
    st.title("FHSIS Portal")
    
    # RBAC: Check for Admin Access in Session State
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False
        
    nav_options = [
        "🏠 Home", 
        "👶 Immunization Dashboard", 
        "🩺 NCD Dashboard", 
        "🚰 WASH Dashboard", 
        "🤰 Maternal Dashboard", 
        "👨‍👩‍👧 Family Planning Dashboard",
        "💀 Mortality Dashboard", 
        "📈 YoY Comparison"
    ]

    # Only show the Uploader if unlocked
    if st.session_state["is_admin"]:
        nav_options.append("📁 Data Uploader")
        
    # 1. CREATE NAVIGATION FIRST
    page = st.radio("Navigation", nav_options)
    st.markdown("---")
    
    # 2. RUN FILTERS BASED ON THE SELECTED PAGE
    if page in ["👶 Immunization Dashboard", "🩺 NCD Dashboard", "📈 YoY Comparison", "🚰 WASH Dashboard", "🤰 Maternal Dashboard", "👨‍👩‍👧 Family Planning Dashboard", "💀 Mortality Dashboard"]:
        st.subheader("🎛️ Global Filters")
        selected_year = st.selectbox("Select Year", options=[2021, 2022, 2023, 2024, 2025, 2026, 2027], index=4)
        
        # --- CONTEXT-AWARE GENDER FILTER ---
        if page != "👨‍👩‍👧 Family Planning Dashboard":
            gender_filter = st.selectbox("Select Demographic", options=["Total", "Male", "Female"])
        else:
            # Silently lock the variable to "Total" in the background for Family Planning
            gender_filter = "Total"
            
        rhu_filter = st.multiselect("Select RHU(s)", options=["Abra (Total)"] + ABRA_RHUS, default=["Abra (Total)"])
        
        # Determine the location header dynamically
        if not rhu_filter or "Abra (Total)" in rhu_filter:
            location_header = "📍 Abra Province (Total)"
        else:
            loc_text = ", ".join(rhu_filter)
            location_header = f"📍 {loc_text}" if len(loc_text) < 45 else f"📍 {len(rhu_filter)} Selected RHUs"
            
    # Admin Login Expander at the bottom of the sidebar
    st.markdown("---")
    if not st.session_state["is_admin"]:
        with st.expander("🔒 Admin Access"):
            admin_pw = st.text_input("Enter Password", type="password", key="sidebar_pw")
            if admin_pw == st.secrets.get("admin_password", "AbraAdmin2026"):
                st.session_state["is_admin"] = True
                st.rerun()
            elif admin_pw:
                st.error("Incorrect password")
    else:
        if st.button("🔓 Logout Admin", use_container_width=True):
            st.session_state["is_admin"] = False
            st.rerun()

# --- FILTERING HELPERS ---
def get_filtered_data(app_key, year, rhus):
    if 'fhsis_data' not in st.session_state or app_key not in st.session_state['fhsis_data']:
        return pd.DataFrame()
    df = st.session_state['fhsis_data'][app_key]
    if df.empty: return df
    
    df_filtered = df[df['Year'].astype(str) == str(year)]
    if not rhus or "Abra (Total)" in rhus:
        pass 
    else:
        df_filtered = df_filtered[df_filtered['Area'].isin(rhus)]
    return df_filtered

# --- DASHBOARD ROUTING & UI ---
if page == "🏠 Home":
    st.title("🏥 Abra Provincial Health Office - FHSIS Command Center")
    st.markdown("""
        Welcome to the central hub for the Field Health Services Information System (FHSIS) of Abra Province. 
        This portal automatically tracks, cleans, and visualizes health data across all 27 Rural Health Units.
    """)
    
    st.info("👈 **Use the sidebar to navigate between specific health modules and apply global filters.**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total RHUs Tracked", len(ABRA_RHUS))
    with col2:
        st.metric("Data Modules Active", "6")
    with col3:
        st.metric("System Status", "Live & Synced")
        
    st.markdown("---")
    st.subheader("Provincial Coverage Map")
    
    # Simple Scatter Map for Abra RHUs
    map_data = pd.DataFrame([
        {"RHU": name, "lat": coords[0], "lon": coords[1]} 
        for name, coords in ABRA_COORDS.items()
    ])
    fig_map = px.scatter_mapbox(
        map_data, lat="lat", lon="lon", hover_name="RHU",
        color_discrete_sequence=["#7209b7"], zoom=9, center={"lat": 17.58, "lon": 120.75}
    )
    fig_map.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

elif page == "👶 Immunization Dashboard":
    st.title("👶 Child Immunization Dashboard")
    st.subheader(location_header)
    
    df_penta = get_filtered_data("Penta", selected_year, rhu_filter)
    df_mmr = get_filtered_data("MMR", selected_year, rhu_filter)
    
    if df_penta.empty and df_mmr.empty:
        st.warning(f"No Immunization data available for {selected_year} in the selected RHUs.")
    else:
        # Calculate Metrics
        total_penta = df_penta['Total Penta 3_Total'].sum() if not df_penta.empty and 'Total Penta 3_Total' in df_penta.columns else 0
        total_mmr = df_mmr['Total MMR 2_Total'].sum() if not df_mmr.empty and 'Total MMR 2_Total' in df_mmr.columns else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Total Penta 3 Doses", value=f"{total_penta:,.0f}")
        with col2:
            st.metric(label="Total MMR 2 Doses", value=f"{total_mmr:,.0f}")
            
        st.markdown("---")
        if not df_penta.empty and 'Total Penta 3_Total' in df_penta.columns:
            st.subheader("Penta 3 Administration by RHU")
            rhu_penta = df_penta.groupby('Area')['Total Penta 3_Total'].sum().reset_index()
            fig = px.bar(rhu_penta, x='Area', y='Total Penta 3_Total', title="Penta 3 Doses by Municipality", color_discrete_sequence=['#4361ee'])
            st.plotly_chart(fig, use_container_width=True)

elif page == "🩺 NCD Dashboard":
    st.title("🩺 Non-Communicable Diseases (NCD)")
    st.subheader(location_header)
    
    df_adults = get_filtered_data("Adults_Risk", selected_year, rhu_filter)
    
    if df_adults.empty:
        st.warning(f"No NCD data available for {selected_year} in the selected RHUs.")
    else:
        # Dynamic gender filtering for metrics
        if gender_filter == "Total":
            col_name = "Total Risk Assessed_Total"
        elif gender_filter == "Male":
            col_name = "Total Risk Assessed_Male"
        else:
            col_name = "Total Risk Assessed_Female"
            
        total_assessed = df_adults[col_name].sum() if col_name in df_adults.columns else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label=f"Adults Risk Assessed ({gender_filter})", value=f"{total_assessed:,.0f}")
        with col2:
            st.metric(label="Cervical Cancer Screenings", value="See Charts")
        with col3:
            st.metric(label="Breast Cancer Screenings", value="See Charts")

        st.markdown("---")
        if col_name in df_adults.columns:
            st.subheader(f"Adult Risk Assessment Trends ({selected_year})")
            trend_data = df_adults.groupby('Month')[col_name].sum().reset_index()
            # Sort months chronologically
            months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            trend_data['Month'] = pd.Categorical(trend_data['Month'], categories=months_order, ordered=True)
            trend_data = trend_data.sort_values('Month')
            
            fig = px.line(trend_data, x='Month', y=col_name, markers=True, title="Monthly Risk Assessments", color_discrete_sequence=['#f72585'])
            st.plotly_chart(fig, use_container_width=True)

elif page == "🚰 WASH Dashboard":
    st.title("🚰 Water, Sanitation, and Hygiene (WASH)")
    st.subheader(location_header)
    
    df_water = get_filtered_data("Safe_Water", selected_year, rhu_filter)
    df_san = get_filtered_data("Sanitation", selected_year, rhu_filter)
    
    if df_water.empty and df_san.empty:
        st.warning(f"No WASH data available for {selected_year} in the selected RHUs.")
    else:
        col1, col2 = st.columns(2)
        
        water_target = "HH with Access to Basic Safe Water Supply"
        total_safe_water = df_water[water_target].max() if not df_water.empty and water_target in df_water.columns else 0
        
        san_target = "HH with Basic Sanitation Facility"
        total_sanitation = df_san[san_target].max() if not df_san.empty and san_target in df_san.columns else 0
        
        with col1:
            st.metric(label="HHs with Safe Water Supply", value=f"{total_safe_water:,.0f}")
        with col2:
            st.metric(label="HHs with Basic Sanitation", value=f"{total_sanitation:,.0f}")
            
        st.markdown("---")
        if not df_water.empty and water_target in df_water.columns:
            st.subheader("Safe Water Access by RHU")
            # Take the max value per RHU for the year (since WASH is cumulative quarterly)
            rhu_water = df_water.groupby('Area')[water_target].max().reset_index()
            fig = px.bar(rhu_water, x='Area', y=water_target, title="Safe Water Households by Municipality", color_discrete_sequence=['#4cc9f0'])
            st.plotly_chart(fig, use_container_width=True)

elif page == "🤰 Maternal Dashboard":
    st.title("🤰 Maternal Health Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Time Filter")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("Time Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed", key="mat_time")
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"), label_visibility="collapsed", key="mat_m")
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"), label_visibility="collapsed", key="mat_q")
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
            
    st.markdown("##### 👩 Age Filter")
    age_filter = st.selectbox("Isolate Specific Demographic", ["Total", "10-14", "15-19", "20-49"])
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    mat_tab1, mat_tab2, mat_tab3, mat_tab4, mat_tab5, mat_tab6 = st.tabs([
        "🩺 Antenatal Care", 
        "🥗 Nutritional & Td",
        "💊 Calcium & Deworming",
        "🦠 Syphilis & Hep B",
        "🩸 CBC & Gestational",
        "👶 Postpartum Care"
    ])
    
    with mat_tab1: render_maternal_tab("Antenatal Care (ANC)", "ANC", start_month, end_month, selected_year, age_filter, rhu_filter)
    with mat_tab2: render_maternal_tab("Nutritional Status", "Nutritional_Status", start_month, end_month, selected_year, age_filter, rhu_filter)
    with mat_tab3: render_maternal_tab("Calcium & Deworming", "Calcium_MMS", start_month, end_month, selected_year, age_filter, rhu_filter)
    with mat_tab4: render_maternal_tab("Syphilis & Hep B", "Syphilis_HepB", start_month, end_month, selected_year, age_filter, rhu_filter)
    with mat_tab5: render_maternal_tab("CBC & Gestational Diabetes", "CBC_Gestational", start_month, end_month, selected_year, age_filter, rhu_filter)
    with mat_tab6: render_maternal_tab("Postpartum Care (PPC)", "PPC", start_month, end_month, selected_year, age_filter, rhu_filter)

elif page == "👨‍👩‍👧 Family Planning Dashboard":
    st.title("👨‍👩‍👧 Family Planning (FP) Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Time Filter")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("Time Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed", key="fp_time")
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"), label_visibility="collapsed", key="fp_m")
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"), label_visibility="collapsed", key="fp_q")
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
            
    st.markdown("##### 👩 Age Filter")
    age_filter = st.selectbox("Isolate Specific Demographic", ["Total", "10-14", "15-19", "20-49"], key="fp_age")
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    fp_tab1, fp_tab2, fp_tab3 = st.tabs(["🌟 CPR & Demand Satisfied", "🔄 User Pipeline (Flow)", "💊 Method Mix (Preferences)"])
    
    # Helper to filter FP data
    def get_fp_filtered(df_key, sm, em, yr, rhus):
        if df_key not in st.session_state['fhsis_data']: return pd.DataFrame()
        df = st.session_state['fhsis_data'][df_key]
        df_yr = df[df['Year'] == yr]
        
        m_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        s_idx = m_order.index(sm)
        e_idx = m_order.index(em)
        v_months = m_order[s_idx:e_idx+1]
        
        filt = df_yr[df_yr['Month'].isin(v_months)]
        if rhus and "Abra (Total)" not in rhus:
            filt = filt[filt['Area'].isin(rhus)]
        return filt

    with fp_tab1:
        st.markdown("### 🌟 Program Overview: CPR & Demand Satisfied")
        
        # --- NEW: Clarification for Age Filter ---
        if age_filter != "Total":
            st.info(f"💡 **Note:** Demand Satisfied and CPR metrics are calculated using the entire baseline of Women of Reproductive Age (15-49). Therefore, the '{age_filter}' demographic filter does not alter the overall provincial CPR.")
            
        df_dem = get_fp_filtered("FP_Demand", start_month, end_month, selected_year, rhu_filter)
        
        if not df_dem.empty:
            latest_month = df_dem['Month'].iloc[-1]
            df_latest = df_dem[df_dem['Month'] == latest_month]
            
            dem_target = df_latest['Total Demand Factor'].sum() if 'Total Demand Factor' in df_latest.columns else 0
            curr_users = df_latest['Total Current User'].sum() if 'Total Current User' in df_latest.columns else 0
            
            prov_cpr = (curr_users / dem_target * 100) if dem_target > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total WRA with Demand (Denominator)", f"{int(dem_target):,}")
            c2.metric(f"Current FP Users ({latest_month})", f"{int(curr_users):,}")
            c3.metric(f"Contraceptive Prev. Rate (CPR)", f"{prov_cpr:.1f}%")
            
            st.markdown("---")
            if 'Demand Satisfied' in df_latest.columns and 'CPR' in df_latest.columns:
                rhu_perf = df_latest.groupby('Area')[['Demand Satisfied', 'CPR']].mean().reset_index()
                
                fig_cpr = px.bar(rhu_perf.sort_values('CPR', ascending=False), x='Area', y='CPR', 
                                 title=f"Contraceptive Prevalence Rate (CPR) by RHU - {latest_month}",
                                 text_auto='.1f', color='CPR', color_continuous_scale="Purples")
                fig_cpr.update_layout(xaxis_title="RHU", yaxis_title="CPR (%)", margin=dict(t=40))
                st.plotly_chart(fig_cpr, use_container_width=True)
        else:
            st.info("No Demand Satisfied data available for the selected period.")

    with fp_tab2:
        st.markdown("### 🔄 Family Planning User Pipeline")
        st.markdown("Visualizing the monthly flow of acceptors joining and dropping out of the program.")
        
        fp_methods = [
            "All Methods (Overall)", "Condom", "PILLS-POP", "PILLS-COC", "Injectables", 
            "Implants-Interval", "Implants-PP", "IUD-I", "IUD-PP", "FSTR/BTL", 
            "MSTR/NSV", "NFP-LAM", "NFP-BBT", "NFP-CMM", "NFP-STM", "NFP-SDM"
        ]
        selected_method = st.selectbox("🎯 Select Contraceptive Method to Track:", fp_methods, key="fp_method_drilldown")
        
        df_beg = get_fp_filtered("FP_Beginning", start_month, end_month, selected_year, rhu_filter)
        df_new = get_fp_filtered("FP_New", start_month, end_month, selected_year, rhu_filter)
        df_oth = get_fp_filtered("FP_Other", start_month, end_month, selected_year, rhu_filter)
        df_drp = get_fp_filtered("FP_Dropouts", start_month, end_month, selected_year, rhu_filter)
        df_end = get_fp_filtered("FP_End", start_month, end_month, selected_year, rhu_filter)
        
        # --- NEW: Smart Value Extractor ---
        # This solves the DOH Excel quirk by manually summing up all methods if an age filter is active
        def get_fp_value(df, method, age):
            if df.empty: return 0
            if method == "All Methods (Overall)":
                if age == "Total":
                    if "Total Current User" in df.columns: return df["Total Current User"].sum()
                    return 0
                else:
                    # Dynamically add up ALL individual methods for this specific age!
                    age_cols = [c for c in df.columns if c.endswith(f"_{age}") and "Total Current" not in c and "%" not in c]
                    return df[age_cols].sum().sum()
            else:
                target = f"{method}_{age}"
                if target in df.columns: return df[target].sum()
                
                # Fallback search
                cols = [c for c in df.columns if method in c and age in c and "%" not in c]
                if cols: return df[cols[0]].sum()
                return 0

        if not df_end.empty and not df_beg.empty:
            try:
                v_beg = get_fp_value(df_beg, selected_method, age_filter)
                v_new = get_fp_value(df_new, selected_method, age_filter)
                v_oth = get_fp_value(df_oth, selected_method, age_filter)
                v_drp = get_fp_value(df_drp, selected_method, age_filter)
                v_end = get_fp_value(df_end, selected_method, age_filter)
                
                step1, step2, step3, step4, step5 = v_beg, v_beg + v_new, v_beg + v_new + v_oth, v_beg + v_new + v_oth - v_drp, v_end
                y_max = max(step1, step2, step3, step4, step5)
                y_min = min(step1, step2, step3, step4, step5)
                
                padding = (y_max - y_min) * 0.15
                if padding == 0: padding = y_max * 0.1
                custom_y_range = [max(0, y_min - padding), y_max + padding]

                wf_data = pd.DataFrame({
                    "Stage": ["Beginning Users", "New Acceptors", "Other Acceptors", "Dropouts", "End Users"],
                    "Value": [v_beg, v_new, v_oth, -v_drp, v_end],
                    "Measure": ["absolute", "relative", "relative", "relative", "total"]
                })
                
                import plotly.graph_objects as go
                fig_waterfall = go.Figure(go.Waterfall(
                    name = "FP Pipeline", orientation = "v", measure = wf_data["Measure"],
                    x = wf_data["Stage"], textposition = "outside",
                    text = wf_data["Value"].astype(int).apply(lambda x: f"{x:,}"), y = wf_data["Value"],
                    connector = {"line":{"color":"rgb(63, 63, 63)"}}, decreasing = {"marker":{"color":"#EF553B"}},
                    increasing = {"marker":{"color":"#00CC96"}}, totals = {"marker":{"color":"#636EFA"}}
                ))
                
                fig_waterfall.update_layout(
                    title=f"Pipeline Flow: {selected_method} ({age_filter})", 
                    margin=dict(t=50), yaxis=dict(range=custom_y_range)
                )
                st.plotly_chart(fig_waterfall, use_container_width=True)
                
            except Exception as e:
                st.warning(f"Could not calculate waterfall pipeline for '{selected_method}' ({age_filter}).")
        else:
            st.info("Upload Beginning, New, Other, Dropouts, and End data to view the pipeline.")

    with fp_tab3:
        st.markdown("### 💊 Method Mix (Contraceptive Preferences)")
        df_end_mix = get_fp_filtered("FP_End", start_month, end_month, selected_year, rhu_filter)
        
        if not df_end_mix.empty:
            # --- NEW: Fixed "Total" Logic Paradox ---
            if age_filter == "Total":
                method_cols = [c for c in df_end_mix.columns if c.endswith("_Total") and "Total Current" not in c and "%" not in c]
            else:
                method_cols = [c for c in df_end_mix.columns if c.endswith(f"_{age_filter}") and "Total Current" not in c and "%" not in c]
            
            if method_cols:
                mix_dict = {c.replace(f"_{age_filter}", "").strip(): df_end_mix[c].sum() for c in method_cols}
                mix_df = pd.DataFrame(list(mix_dict.items()), columns=['Method', 'Users'])
                mix_df = mix_df[mix_df['Users'] > 0].sort_values('Users', ascending=False)
                
                col_m1, col_m2 = st.columns([1, 2])
                with col_m1:
                    st.dataframe(mix_df, hide_index=True, use_container_width=True)
                with col_m2:
                    fig_mix = px.pie(mix_df, values='Users', names='Method', hole=0.4, 
                                     title=f"Method Preference Distribution ({age_filter})",
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_mix.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_mix, use_container_width=True)
            else:
                st.warning(f"Could not isolate method columns for the '{age_filter}' demographic.")
        else:
            st.info("No Current Users End data available for the Method Mix.")

elif page == "💀 Mortality Dashboard":
    st.title("💀 Mortality & Injuries Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year} &nbsp; | &nbsp; **👥 Demographic:** {gender_filter}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Time Filter")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("Time Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed", key="mort_time")
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"), label_visibility="collapsed", key="mort_m")
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"), label_visibility="collapsed", key="mort_q")
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    mort_tab1, mort_tab2, mort_tab3 = st.tabs([
        "💔 Premature NCD Deaths", 
        "🚗 Traffic Deaths",
        "💥 Traffic Accidents"
    ])
    
    with mort_tab1: render_mortality_tab("Premature NCD Deaths (30-69 y.o.)", "Premature_NCD", ["total premature", "cvd", "cancer", "diabetes", "respiratory"], start_month, end_month, gender_filter, selected_year, rhu_filter, chart_type="bar")
    with mort_tab2: render_mortality_tab("Traffic Injury Deaths", "Traffic_Deaths", ["traffic injury deaths"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with mort_tab3: render_mortality_tab("Traffic Accidents", "Traffic_Accidents", ["total road accidents"], start_month, end_month, gender_filter, selected_year, rhu_filter)

elif page == "📈 YoY Comparison":
    st.title("⚖️ Year-Over-Year (YoY) Performance")
    if rhu_filter and "Abra (Total)" not in rhu_filter:
        st.markdown(f"**{location_header}**")
    st.markdown("Compare metric performance between two different years to instantly track regional growth or decline.")
    
    col_y1, col_y2, col_y3 = st.columns(3)
    with col_y1:
        yoy_dataset = st.selectbox("Select Data Category", [
            "Birth Doses", "Pentavalent", "Polio", "Pneumococcal (PCV)", "MMR, FIC & CIC",
            "Adults Risk (20-59)", "Seniors Risk (≥60)", "Cervical Cancer", "Breast Cancer",
            "Antenatal Care (ANC)", "Nutritional Status & Td", "Calcium, MMS & Deworming", 
            "Syphilis & Hep B", "CBC & Gestational Diabetes", "Postpartum Care (PPC)", 
            "Livebirths & Deliveries",
            "Premature NCD Deaths", "Traffic Deaths", "Traffic Accidents"
        ])
    with col_y2:
        year_a = st.selectbox("Baseline Year (Year A)", [2021, 2022, 2023, 2024, 2025, 2026, 2027], index=2)
    with col_y3:
        year_b = st.selectbox("Comparison Year (Year B)", [2021, 2022, 2023, 2024, 2025, 2026, 2027], index=3)

    if year_a == year_b:
        st.warning("⚠️ Please select two different years to compare performance.")
    else:
        dataset_keys = {
            "Birth Doses": ("CPAB_BCG_HepB", ["CPAB", "BCG", "Hep"]),
            "Pentavalent": ("Penta", ["DPT", "Penta"]),
            "Polio": ("Polio", ["OPV", "IPV"]),
            "Pneumococcal (PCV)": ("PCV", ["PCV"]),
            "MMR, FIC & CIC": ("MMR", ["MMR", "MCV", "FIC", "CIC"]),
            "Adults Risk (20-59)": ("Adults_Risk", ["risk assessed", "smoking", "smoker", "alcohol", "hypertensive", "type 2 dm"]),
            "Seniors Risk (≥60)": ("Seniors_Risk", ["risk assessed", "smoking", "smoker", "alcohol", "hypertensive", "type 2 dm"]),
            "Cervical Cancer": ("Cervical_Cancer", ["screened", "suspicious", "positive", "lesions"]),
            "Breast Cancer": ("Breast_Cancer", ["early detection", "asymptomatic", "remarkable", "linked"]),
            "Antenatal Care (ANC)": ("ANC", ['new pregnant', 'least 4 anc', 'tracked during pregnancy (a)', '8th anc on schedule', 'least 8anc (a+b)']),
            "Nutritional Status & Td": ("Nutritional_Status", ["assessed of their nutritional status", "1st time given at least 2 doses of td", "2nd or more times given at least 3 doses of td", "iron w/ folic acid"]),
            "Calcium, MMS & Deworming": ("Calcium_MMS", ("calcium carbonate", "multiple micronutrient", "deworming tablet")),
            "Syphilis & Hep B": ("Syphilis_HepB", ["screened for syphilis", "tested positive for syphilis", "screened for hepatitis b", "reactive to hepatitis b", "screened for hiv", "reactive to hiv"]),
            "CBC & Gestational Diabetes": ("CBC_Gestational", ["tested for cbc/hgb/hct", "diagnosed with anemia", "screened for gestational diabetes", "positive for gestational diabetes"]),
            "Postpartum Care (PPC)": ("PPC", ['2 postpartum check-ups', 'pp women who were tracked (a)', '4th pnc on schedule', 'least 4pnc =(a+b)', 'iron with folic', 'vitamin a']),
            "Livebirths & Deliveries": ("Livebirths", ["total deliveries", "total livebirths"]),
            "Premature NCD Deaths": ("Premature_NCD", ["deaths", "premature"]),
            "Traffic Deaths": ("Traffic_Deaths", ["deaths", "traffic", "injury"]),
            "Traffic Accidents": ("Traffic_Accidents", ["accidents", "traffic", "road"])
        }
        df_key, base_mets = dataset_keys[yoy_dataset]
        
        is_ncd = yoy_dataset in ["Adults Risk (20-59)", "Seniors Risk (≥60)", "Cervical Cancer", "Breast Cancer"]
        is_maternal = yoy_dataset in ["Antenatal Care (ANC)", "Postpartum Care (PPC)", "Livebirths & Deliveries", "Nutritional Status & Td", "Calcium, MMS & Deworming", "Syphilis & Hep B", "CBC & Gestational Diabetes"]
        is_cancer_dataset = yoy_dataset in ["Cervical Cancer", "Breast Cancer"]

        if is_cancer_dataset and gender_filter == "Male":
            st.info("🎗️ Cancer screening data is exclusively tracked for the Female demographic. Please switch the Global Filter to 'Female' or 'Total'.")
        elif df_key in st.session_state['fhsis_data']:
            raw_df = st.session_state['fhsis_data'][df_key]
            available_cols = []
            
            if is_ncd or is_maternal:
                for base in base_mets:
                    group_cols = []
                    for col in raw_df.columns:
                        clean_c = col.replace('\n', ' ').lower()
                        if base.lower() in clean_c and "%" not in col and "deficit" not in clean_c and "previous" not in clean_c:
                            is_valid_gender = False
                            if is_cancer_dataset:
                                is_valid_gender = True
                            elif is_maternal:
                                if col.lower().endswith("total") or "_total" in col.lower() or not (col.endswith("_10-14") or col.endswith("_15-19") or col.endswith("_20-49")):
                                    is_valid_gender = True
                            else:
                                if gender_filter == "Total":
                                    if col.endswith("_Total") or not (col.endswith("_Male") or col.endswith("_Female")):
                                        is_valid_gender = True
                                else:
                                    if col.endswith(f"_{gender_filter}"):
                                        is_valid_gender = True
                                        
                            if is_valid_gender:
                                group_cols.append(col)
                                
                    if group_cols:
                        total_cols = [c for c in group_cols if "total" in c.lower()]
                        if total_cols: 
                            if total_cols[0] not in available_cols: available_cols.append(total_cols[0])
                        else: 
                            best_c = max(group_cols, key=lambda c: pd.to_numeric(raw_df[c], errors='coerce').sum())
                            if best_c not in available_cols: available_cols.append(best_c)
            else:
                for base in base_mets:
                    for col in raw_df.columns:
                        if base.lower() in col.lower() and "%" not in col and "deficit" not in col.lower() and "previous" not in col.lower():
                            is_valid = False
                            if gender_filter == "Total":
                                if col.endswith("_Total") or not (col.endswith("_Male") or col.endswith("_Female")):
                                    is_valid = True
                            else:
                                if col.endswith(f"_{gender_filter}"):
                                    is_valid = True
                            if is_valid and col not in available_cols:
                                available_cols.append(col)

            if available_cols:
                compare_col = st.selectbox("🎯 Select Specific Indicator to Compare", available_cols, format_func=get_clean_indicator_name, key=f"yoy_select_{yoy_dataset}_{gender_filter}_{year_a}_{year_b}")

                if 'Year' in raw_df.columns:
                    df_a = raw_df[raw_df['Year'] == year_a]
                    df_b = raw_df[raw_df['Year'] == year_b]
                    
                    rhu_list = ABRA_RHUS
                    if rhu_filter and "Abra (Total)" not in rhu_filter:
                        df_a = df_a[df_a['Area'].isin(rhu_filter)]
                        df_b = df_b[df_b['Area'].isin(rhu_filter)]
                        rhu_list = rhu_filter
                    
                    agg_a = df_a.groupby('Area')[compare_col].sum().reset_index().rename(columns={compare_col: f'{year_a}'})
                    agg_b = df_b.groupby('Area')[compare_col].sum().reset_index().rename(columns={compare_col: f'{year_b}'})

                    merged = pd.merge(pd.DataFrame({'Area': rhu_list}), agg_a, on='Area', how='left').fillna(0)
                    merged = pd.merge(merged, agg_b, on='Area', how='left').fillna(0)
                    merged['Variance'] = merged[f'{year_b}'] - merged[f'{year_a}']
                    
                    st.markdown("---")
                    st.markdown("#### 🏆 Performance Insights")
                    c_win, c_loss = st.columns(2)
                    
                    # Calculate Percentage Change for better context
                    merged['% Change'] = np.where(merged[f'{year_a}'] > 0, (merged['Variance'] / merged[f'{year_a}']) * 100, 0)
                    
                    top_improvers = merged.nlargest(3, 'Variance')
                    with c_win:
                        st.success("**Top Most Improved RHUs (Absolute Increase)**")
                        for idx, row in top_improvers.iterrows():
                            if row['Variance'] > 0:
                                st.markdown(f"- **{row['Area']}:** +{int(row['Variance'])} counts ({row['% Change']:+.1f}%)")
                            
                    bottom_drops = merged.nsmallest(3, 'Variance')
                    with c_loss:
                        st.error("**Action Required: Steepest Declines**")
                        for idx, row in bottom_drops.iterrows():
                            if row['Variance'] < 0:
                                st.markdown(f"- **{row['Area']}:** {int(row['Variance'])} counts ({row['% Change']:+.1f}%)")

                    st.markdown("---")
                    st.markdown(f"#### 📊 {get_clean_indicator_name(compare_col)} : {year_a} vs {year_b}")

                    # Sort by Year B volume for a clean descending staircase effect
                    merged_sorted_vol = merged.sort_values(by=f'{year_b}', ascending=False)
                    melted_yoy = merged_sorted_vol.melt(id_vars='Area', value_vars=[f'{year_a}', f'{year_b}'], var_name='Year', value_name='Counts')
                    
                    fig_yoy = px.bar(melted_yoy, x='Area', y='Counts', color='Year', barmode='group',
                                     title=f"Head-to-Head Comparison: {year_a} vs {year_b} (Sorted by {year_b} Volume)", 
                                     text_auto=True, color_discrete_sequence=["#1f77b4", "#ff7f0e"])
                    fig_yoy.update_traces(textfont_size=11, textposition="outside", cliponaxis=False)
                    fig_yoy.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Number of Counts", margin=dict(t=40))
                    st.plotly_chart(fig_yoy, use_container_width=True, key=f"yoy_bar_{compare_col}_{year_a}_{year_b}")

                    st.markdown(f"#### 📈 Growth / Decline (Variance)")
                    
                    # Sort by Variance and flip horizontally for a readable Diverging Bar Chart
                    merged_sorted_var = merged.sort_values('Variance', ascending=True)
                    merged_sorted_var['Color'] = np.where(merged_sorted_var['Variance'] >= 0, 'Growth (Positive)', 'Decline (Negative)')
                    
                    fig_var = px.bar(merged_sorted_var, x='Variance', y='Area', orientation='h', color='Color', 
                                     text='Variance', hover_data={'% Change': ':.1f'},
                                     color_discrete_map={'Growth (Positive)': '#2CA02C', 'Decline (Negative)': '#D62728'},
                                     title=f"Net Change in Counts ({year_b} minus {year_a})")
                    fig_var.update_traces(textposition="outside", cliponaxis=False)
                    fig_var.update_layout(xaxis_title="Difference in Counts", yaxis_title="Rural Health Unit (RHU)", margin=dict(t=40, l=0, r=0), height=700)
                    st.plotly_chart(fig_var, use_container_width=True, key=f"yoy_var_{compare_col}_{year_a}_{year_b}")

                    with st.expander("📄 View Detailed YoY Data Table", expanded=True):
                        display_df = merged[['Area', f'{year_a}', f'{year_b}', 'Variance', '% Change']].copy()
                        display_df['% Change'] = display_df['% Change'].round(1).astype(str) + '%'
                        display_df['Trend'] = np.where(display_df['Variance'] > 0, '🟢 Improved', np.where(display_df['Variance'] < 0, '🔴 Declined', '⚫ Stable'))
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.warning("Historical data missing 'Year' tags. Please re-upload your files and select the year.")
            else:
                st.warning("No indicator columns found for this category.")
        else:
            st.info("No data available for this category yet. Go to Data Uploader to push your FHSIS files.")

elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.info("🔒 The Data Uploader is active. You are logged in as Admin.")
        
    st.markdown("Upload your FHSIS Excel files here. The app extracts all 12 monthly sheets, filters for Abra's 27 RHUs, and saves them to Google Sheets.")
    upload_year = st.selectbox("📅 Select Year for these uploads (Important for historical tracking):", [2021, 2022, 2023, 2024, 2025, 2026, 2027], index=4)
    
    upload_tab_imm, upload_tab_ncd, upload_tab_wash, upload_tab_mat, upload_tab_mort, upload_tab_fp = st.tabs(["👶 Child Immunization", "🩺 NCD", "🚰 WASH", "🤰 Maternal Health", "💀 Mortality & Injuries", "👨‍👩‍👧 Family Planning"])
    
    with upload_tab_imm:
        st.markdown("##### Upload Immunization Excel Templates")
        col1, col2 = st.columns(2)
        with col1:
            file_cpab = st.file_uploader("Upload: 1 CPAB, BCG and Hepa B", type=["csv", "xlsx"])
            file_penta = st.file_uploader("Upload: 2 DPT-HiB-HepB", type=["csv", "xlsx"])
            file_polio = st.file_uploader("Upload: 3 OPV and IPV", type=["csv", "xlsx"])
        with col2:
            file_pcv = st.file_uploader("Upload: 4 PCV", type=["csv", "xlsx"])
            file_mmr = st.file_uploader("Upload: 5 MMR, FIC and CIC", type=["csv", "xlsx"])
            
        if st.button("☁️ Save Immunization Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_cpab: upload_dict["CPAB_BCG_HepB"] = load_and_clean_fhsis_data(file_cpab, upload_year)
            if file_penta: upload_dict["Penta"] = load_and_clean_fhsis_data(file_penta, upload_year)
            if file_polio: upload_dict["Polio"] = load_and_clean_fhsis_data(file_polio, upload_year)
            if file_pcv: upload_dict["PCV"] = load_and_clean_fhsis_data(file_pcv, upload_year)
            if file_mmr: upload_dict["MMR"] = load_and_clean_fhsis_data(file_mmr, upload_year)
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} Immunization Files safely merged into Google Sheets!", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")
                
    with upload_tab_ncd:
        st.markdown("##### Upload NCD Excel Templates")
        st.info("💡 **2024 Upload Tip:** If you are using the 2024 combined 'Cervical Cancer & Breast Mass' template, upload that exact same file into BOTH the Cervical and Breast Cancer upload slots below.")
        col3, col4 = st.columns(2)
        with col3:
            file_adults = st.file_uploader("Upload: 1 Adults Risk Assessed", type=["csv", "xlsx"])
            file_seniors = st.file_uploader("Upload: 2 Seniors Risk Assessed", type=["csv", "xlsx"])
        with col4:
            file_cervical = st.file_uploader("Upload: 5 Cervical Cancer (or 24 Combined)", type=["csv", "xlsx"])
            file_breast = st.file_uploader("Upload: 6 Breast Cancer (or 24 Combined)", type=["csv", "xlsx"])
            
        if st.button("☁️ Save NCD Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_adults: upload_dict["Adults_Risk"] = load_and_clean_ncd_data(file_adults, upload_year)
            if file_seniors: upload_dict["Seniors_Risk"] = load_and_clean_ncd_data(file_seniors, upload_year)
            if file_cervical: upload_dict["Cervical_Cancer"] = load_and_clean_ncd_data(file_cervical, upload_year)
            if file_breast: upload_dict["Breast_Cancer"] = load_and_clean_ncd_data(file_breast, upload_year)
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} NCD Files safely merged! Head over to the NCD Dashboard.", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")

    with upload_tab_wash:
        st.markdown("##### Upload WASH Excel Templates")
        st.info("💡 **Tip:** The engine automatically detects Q1, Q2, Q3, and Q4 tabs from your uploaded files.")
        
        file_safe_water = st.file_uploader("Upload: Environmental 1 - Safe Water", type=["csv", "xlsx"])
        file_sanitation = st.file_uploader("Upload: Environmental 2 - Sanitation", type=["csv", "xlsx"])
        
        if st.button("☁️ Save WASH Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_safe_water: upload_dict["Safe_Water"] = load_and_clean_wash_data(file_safe_water, upload_year)
            if file_sanitation: upload_dict["Sanitation"] = load_and_clean_wash_data(file_sanitation, upload_year)
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} WASH Files safely merged! Head over to the WASH Dashboard.", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")

    with upload_tab_mat:
        st.markdown("##### Upload Maternal Health Excel Templates")
        col5, col6, col7 = st.columns(3)
        with col5:
            file_anc = st.file_uploader("Upload: 1 4ANC and 8ANC", type=["csv", "xlsx"])
            file_nutri = st.file_uploader("Upload: 2 Nutritional Status, Td & Iron", type=["csv", "xlsx"])
            file_calcium = st.file_uploader("Upload: 3 Calcium, MMS & Deworming", type=["csv", "xlsx"])
        with col6:
            file_syphilis = st.file_uploader("Upload: 4 Syphilis & Hep B", type=["csv", "xlsx"])
            file_cbc = st.file_uploader("Upload: 5 CBC & Gestational Diabetes", type=["csv", "xlsx"])
            file_ppc = st.file_uploader("Upload: 7 Postpartum Care", type=["csv", "xlsx"])
        with col7:
            file_lb = st.file_uploader("Upload: 6 Livebirths & Deliveries", type=["csv", "xlsx"])
            
        if st.button("☁️ Save Maternal Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_anc: upload_dict["ANC"] = load_and_clean_maternal_data(file_anc, upload_year, "ANC")
            if file_nutri: upload_dict["Nutritional_Status"] = load_and_clean_maternal_data(file_nutri, upload_year, "Nutritional")
            if file_calcium: upload_dict["Calcium_MMS"] = load_and_clean_maternal_data(file_calcium, upload_year, "Calcium")
            if file_syphilis: upload_dict["Syphilis_HepB"] = load_and_clean_maternal_data(file_syphilis, upload_year, "Syphilis")
            if file_cbc: upload_dict["CBC_Gestational"] = load_and_clean_maternal_data(file_cbc, upload_year, "CBC")
            if file_ppc: upload_dict["PPC"] = load_and_clean_maternal_data(file_ppc, upload_year, "PPC")
            if file_lb: upload_dict["Livebirths"] = load_and_clean_maternal_data(file_lb, upload_year, "Livebirths")
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} Maternal Files safely merged into Google Sheets!", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")
                
    with upload_tab_mort:
        st.markdown("##### Upload F1 Plus Mortality & Injury Templates")
        file_prem_ncd = st.file_uploader("Upload: F1 Plus 1 Premature NCD Deaths", type=["csv", "xlsx"])
        file_traf_death = st.file_uploader("Upload: F1 Plus 2 Death due to Traffic Injuries", type=["csv", "xlsx"])
        file_traf_acc = st.file_uploader("Upload: F1 Plus 3 No. of Traffic Accidents", type=["csv", "xlsx"])
        
        if st.button("☁️ Save Mortality Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_prem_ncd: upload_dict["Premature_NCD"] = load_and_clean_mortality_data(file_prem_ncd, upload_year)
            if file_traf_death: upload_dict["Traffic_Deaths"] = load_and_clean_mortality_data(file_traf_death, upload_year)
            if file_traf_acc: upload_dict["Traffic_Accidents"] = load_and_clean_mortality_data(file_traf_acc, upload_year)
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} Mortality Files safely merged into Google Sheets!", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")

    with upload_tab_fp:
        st.markdown("##### 👨‍👩‍👧 Upload Family Planning Excel Templates")
        st.info("💡 The FP Module tracks the flow of users: Beginning + New + Other - Dropouts = End.")
        
        col_fp1, col_fp2 = st.columns(2)
        with col_fp1:
            file_fp_beg = st.file_uploader("Upload: 1 Current Users Beginning", type=["csv", "xlsx"])
            file_fp_new = st.file_uploader("Upload: 2 New Acceptors", type=["csv", "xlsx"])
            file_fp_other = st.file_uploader("Upload: 3 Other Acceptors", type=["csv", "xlsx"])
        with col_fp2:
            file_fp_drop = st.file_uploader("Upload: 4 Drop-outs", type=["csv", "xlsx"])
            file_fp_end = st.file_uploader("Upload: 5 Current Users End", type=["csv", "xlsx"])
            file_fp_demand = st.file_uploader("Upload: 6 Demand Satisfied", type=["csv", "xlsx"])
            
        if st.button("☁️ Save Family Planning Data to Cloud", type="primary", use_container_width=True):
            upload_dict = {}
            if file_fp_beg: upload_dict["FP_Beginning"] = load_and_clean_fp_methods(file_fp_beg, upload_year)
            if file_fp_new: upload_dict["FP_New"] = load_and_clean_fp_methods(file_fp_new, upload_year)
            if file_fp_other: upload_dict["FP_Other"] = load_and_clean_fp_methods(file_fp_other, upload_year)
            if file_fp_drop: upload_dict["FP_Dropouts"] = load_and_clean_fp_methods(file_fp_drop, upload_year)
            if file_fp_end: upload_dict["FP_End"] = load_and_clean_fp_methods(file_fp_end, upload_year)
            if file_fp_demand: upload_dict["FP_Demand"] = load_and_clean_fp_demand(file_fp_demand, upload_year)
            
            clean_dict = {k: v for k, v in upload_dict.items() if v is not None}
            if clean_dict:
                save_data_to_gsheets(clean_dict)
                st.toast(f"{upload_year} Family Planning Files safely merged into Google Sheets!", icon="✅")
            else:
                st.toast("No valid data uploaded yet to save.", icon="⚠️")

    st.markdown("---")
    with st.expander("⚠️ Database Management (Danger Zone)"):
        st.warning("Select the specific datasets you want to clear from the cloud database. This will permanently delete their historical data.")
        
        datasets_to_nuke = st.multiselect(
            "Select Datasets to Nuke", 
            options=list(ALL_MAPPINGS.keys()), 
            default=[]
        )
        
        if st.button("🚨 Nuke Selected Data", type="primary"):
            if not datasets_to_nuke:
                st.toast("Please select at least one dataset from the dropdown above to nuke.", icon="⚠️")
            else:
                nuke_cloud_database(datasets_to_nuke)
                st.toast(f"Successfully wiped: {', '.join(datasets_to_nuke)}! Please re-upload your files.", icon="☢️")
                time.sleep(2.5)
                st.rerun()

render_footer()
