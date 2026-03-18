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
    /* 1. Make the active tab visually distinct with DOH-themed purple */
    .stTabs [aria-selected="true"] {
        color: #7209b7 !important;
        border-bottom-color: #7209b7 !important;
    }
    
    /* 2. ELEVATED METRIC CARDS */
    /* This applies a sleek, modern card look to all your big numbers */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        transition: transform 0.2s ease-in-out;
    }
    
    /* Add a slight hover effect so the cards feel interactive */
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Dark mode support for the cards */
    @media (prefers-color-scheme: dark) {
        [data-testid="stMetric"] {
            background-color: #1e1e1e;
            border-color: #333333;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
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
            # Note: Depending on your Streamlit version, accessing headers might vary slightly.
            # In newer versions, st.context.headers works perfectly.
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
                # Silently pass so a database error doesn't crash the UI for the user
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

# Ensure FP_MAPPING is added to the ALL_MAPPINGS dictionary:
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
                # 1. Read existing data
                try:
                    existing_df = conn.read(worksheet=sheet_name, ttl=0)
                    if not existing_df.empty and 'Area' in existing_df.columns:
                        existing_df = existing_df.dropna(subset=['Area', 'Year'])
                    else:
                        existing_df = pd.DataFrame()
                except Exception:
                    existing_df = pd.DataFrame() 
                
                # 2. Merge logic
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
                    
                # 3. Write data back
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
                
                # 4. SMART CACHE: Update Session State directly to prevent burning a Google API Read Call!
                st.session_state['fhsis_data'][app_key] = combined_df
                
                # 5. Pace the requests to avoid Google's 60 req/min limit
                time.sleep(4) 
                
            except Exception as e:
                st.error(f"❌ Failed to save {sheet_name}. API Error: {e}")
                
    st.cache_data.clear()

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
            # Pace the initial startup loads slightly to prevent crashing on boot
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
@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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
@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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
        
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

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
    
    # --- LAZY LOADING CLOUD DATA ---
    # If they are on the Home page, skip the download so it boots instantly!
    # If they click a dashboard, trigger the sync (and cache it for later).
    if page != "🏠 Home" and 'fhsis_data' not in st.session_state:
        with st.spinner(f"🔄 Syncing cloud database for the {page}..."):
            st.session_state['fhsis_data'] = load_data_from_gsheets()
    
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

# --- INITIALIZE SESSION STATE (LAZY LOAD) ---
# Skip loading if they are on the Home page so it boots instantly!
if page != "🏠 Home" and 'fhsis_data' not in st.session_state:
    with st.spinner(f"🔄 Syncing cloud database for the {page.replace('👶 ', '').replace('🩺 ', '')}..."):
        st.session_state['fhsis_data'] = load_data_from_gsheets()
        
# --- HELPER FUNCTIONS ---
def filter_data(df, start_month, end_month, gender, year):
    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    start_idx = months_order.index(start_month)
    end_idx = months_order.index(end_month)
    valid_months = months_order[start_idx:end_idx+1]
    
    filtered_df = df[df['Month'].isin(valid_months)]
    if 'Year' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Year'] == year]
        
    cols_to_keep = ['Area', 'Month']
    if 'Year' in filtered_df.columns: cols_to_keep.append('Year')

    for col in filtered_df.columns:
        if col in ['Area', 'Month', 'Year']: continue
        clean_col = col.lower()
        is_valid_gender = False
        
        if gender == "Total":
            if col.endswith("_Total") or not (col.endswith("_Male") or col.endswith("_Female")):
                is_valid_gender = True
        else:
            if col.endswith(f"_{gender}"):
                is_valid_gender = True
                
        if is_valid_gender or "elig" in clean_col or "pop" in clean_col:
            if pd.api.types.is_numeric_dtype(filtered_df[col]):
                if filtered_df[col].sum() > 0: cols_to_keep.append(col)
            else:
                cols_to_keep.append(col)
                
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    if len(cols_to_keep) > 2: return filtered_df[cols_to_keep]
    return filtered_df

def filter_ncd_data(df, start_month, end_month, gender, year, is_cancer=False):
    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    start_idx = months_order.index(start_month)
    end_idx = months_order.index(end_month)
    valid_months = months_order[start_idx:end_idx+1]
    
    filtered_df = df[df['Month'].isin(valid_months)]
    if 'Year' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Year'] == year]
        
    cols_to_keep = ['Area', 'Month']
    if 'Year' in filtered_df.columns: cols_to_keep.append('Year')

    for col in filtered_df.columns:
        if col in ['Area', 'Month', 'Year']: continue
        clean_col = col.lower()
        is_valid_gender = False
        
        if is_cancer:
            is_valid_gender = True
        else:
            if gender == "Total":
                if col.endswith("_Total") or not (col.endswith("_Male") or col.endswith("_Female")):
                    is_valid_gender = True
            else:
                if col.endswith(f"_{gender}"):
                    is_valid_gender = True
                
        if is_valid_gender or "elig" in clean_col or "pop" in clean_col:
            cols_to_keep.append(col)
                
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    if len(cols_to_keep) > 2: return filtered_df[cols_to_keep]
    return filtered_df

def get_ncd_col(df, include_words, exclude_words=None):
    if exclude_words is None: exclude_words = []
    for col in df.columns:
        cl = col.lower().replace('\n', ' ')
        if all(w.lower() in cl for w in include_words) and not any(w.lower() in cl for w in exclude_words):
            return col
    if "no." in [w.lower() for w in include_words]:
        fallback_include = [w for w in include_words if w.lower() != "no."]
        for col in df.columns:
            cl = col.lower().replace('\n', ' ')
            if all(w.lower() in cl for w in fallback_include) and not any(w.lower() in cl for w in exclude_words):
                return col
    return None

def get_clean_indicator_name(col_name):
    c_low = col_name.lower().replace('\n', ' ').replace('-', ' ')
    
    # --- NCD Mapping ---
    if "risk assessed" in c_low: return "Total Risk Assessed"
    if "smoking" in c_low or "smoker" in c_low: return "History of Smoking (Current Smoker)"
    if "alcohol" in c_low: return "Alcohol Binge Drinkers"
    if "obese/ overweight" in c_low or "obese/overweight" in c_low or "obese / overweight" in c_low: return "Obese / Overweight"
    if "overweight" in c_low: return "Overweight"
    if "obese" in c_low: return "Obese"
    if "physical activity" in c_low: return "Insufficient Physical Activity"
    if "unhealthy diet" in c_low: return "Unhealthy Diet"
    if "hypertensive" in c_low: return "Identified Hypertensive"
    if "type 2 dm" in c_low or ("diabetes" in c_low and "gestational" not in c_low): return "Identified Type 2 DM"
    
    # --- Mortality & Injuries Mapping ---
    if "death" in c_low or "deaths" in c_low:
        if "cvd" in c_low or "cardiovascular" in c_low: return "CVD Deaths"
        if "cancer" in c_low: return "Cancer Deaths"
        if "diabetes" in c_low: return "Diabetes Deaths"
        if "respiratory" in c_low: return "Respiratory Disease Deaths"
        if "traffic" in c_low: return "Traffic Injury Deaths"
        if "total" in c_low: return "Total Premature Deaths"
    elif "road accidents" in c_low: return "Total Road Accidents"
    
    # --- Maternal Care (Livebirths Base) ---
    if 'total livebirths' in c_low: return 'Total Livebirths'
    elif 'total deliveries' in c_low:
        if '10 14' in c_low: return '0. Total Deliveries (10-14)'
        elif '15 19' in c_low: return '0. Total Deliveries (15-19)'
        elif '20 49' in c_low: return '0. Total Deliveries (20-49)'
        else: return '0. Total Deliveries'
    
    # --- Maternal Care (ANC) Exact Mapping ---
    elif 'new pregnant' in c_low: return '1. New Pregnant Women Seen'
    elif 'at least 4 anc' in c_low and 'delivered' in c_low: return '2. Delivered with at least 4 ANC visits'
    elif 'gave birth' in c_low and 'tracked' in c_low: return '3. Women gave birth tracked during pregnancy (a)'
    elif 'trans in' in c_low and '8anc' not in c_low and '4pnc' not in c_low and 'pp' not in c_low: return '4. TRANS IN from other LGUs (b)'
    elif 'trans out' in c_low and '8anc' in c_low: return '5. TRANS OUT before completing 8ANC (c)'
    elif '(a+b) c' in c_low and 'delivered' in c_low: return '6. Delivered & tracked during pregnancy (a+b)-c'
    elif '1st to 8th anc' in c_low: return '7. Provided 1st to 8th ANC on schedule (a)'
    elif '8anc' in c_low and 'trans in' in c_low: return '8. Completed 8ANC TRANS IN (b)'
    elif 'at least 8anc (a+b)' in c_low: return '9. Delivered & completed at least 8ANC (a+b)'
    
    # --- Maternal Care (PPC) Exact Mapping ---
    elif '2 postpartum check ups' in c_low: return '2. Completed at least 2 PP check-ups'
    elif 'tracked (a)' in c_low and 'pp women' in c_low: return '3. PP women who were tracked (a)'
    elif 'trans in' in c_low and 'pp' in c_low and '4pnc' not in c_low: return '4. PP women TRANS-IN (b)'
    elif 'trans out' in c_low and 'pp' in c_low: return '5. PP women TRANS-OUT (c)'
    elif '=(a+b) c' in c_low and 'pp' in c_low: return '6. PP Women tracked during pregnancy =(a+b)-c'
    elif '1st to 4th pnc' in c_low: return '7. PP women provided 1st to 4th PNC on schedule (a)'
    elif '4pnc' in c_low and 'trans in' in c_low: return '8. PP women with completed 4PNC TRANS IN (b)'
    elif 'at least 4pnc =(a+b)' in c_low: return '9. Women gave birth completed at least 4PNC =(a+b)'
    elif 'iron with folic' in c_low: return '10. PP women who completed iron with folic acid'
    elif 'vitamin a' in c_low: return '11. PP women given Vitamin A supplementation'

    # --- Nutritional Status (File 2) ---
    elif 'assessed of their nutritional status' in c_low:
        if 'normal bmi' in c_low: return '1. Assessed Nutritional Status (Normal BMI)'
        elif 'low bmi' in c_low: return '1. Assessed Nutritional Status (Low BMI)'
        elif 'high bmi' in c_low: return '1. Assessed Nutritional Status (High BMI)'
        else: return '1. Assessed Nutritional Status'
    elif '1st time given at least 2 doses of td' in c_low: return '2. Given at least 2 doses of Td (1st time)'
    elif '2nd or more times given at least 3 doses of td' in c_low: return '3. Given at least 3 doses of Td (2nd+ time)'
    elif 'completed the dose of iron w/ folic acid' in c_low: return '4. Completed Iron w/ Folic Acid'

    # --- Calcium & Deworming (File 3) ---
    elif 'completed doses of calcium carbonate' in c_low: return '1. Completed Calcium Carbonate'
    elif 'completed the dose multiple micronutrient' in c_low: return '2. Completed MMS'
    elif 'given 1 dose of deworming tablet' in c_low: return '3. Given 1 dose of Deworming Tablet'

    # --- Syphilis & Hep B (File 4) ---
    elif 'screened for syphilis' in c_low: return '1. Screened for Syphilis'
    elif 'tested positive for syphilis' in c_low: return '2. Tested Positive for Syphilis'
    elif 'screened for hepatitis b' in c_low: return '3. Screened for Hepatitis B'
    elif 'screened reactive to hepatitis b' in c_low: return '4. Screened Reactive to Hepatitis B'
    elif 'screened for hiv' in c_low: return '5. Screened for HIV'
    elif 'screened reactive to hiv' in c_low: return '6. Screened Reactive to HIV'

    # --- CBC & Gestational Diabetes (File 5) ---
    elif 'tested for cbc/hgb/hct' in c_low and 'anemia' not in c_low: return '1. Tested for CBC/Hgb/Hct'
    elif 'diagnosed with anemia' in c_low: return '2. Diagnosed with Anemia'
    elif 'screened for gestational diabetes' in c_low: return '3. Screened for Gestational Diabetes'
    elif 'tested positive for gestational diabetes' in c_low: return '4. Tested Positive for Gestational Diabetes'

    # --- Adolescent Birth Rate (File 8) ---
    elif 'adolescent women 10 14' in c_low and 'rate' not in c_low: return '1. Adolescent Women (10-14)'
    elif 'adolescent women 15 19' in c_low and 'rate' not in c_low: return '2. Adolescent Women (15-19)'
    elif 'adolescent women 10 19' in c_low and 'rate' not in c_low: return '3. Adolescent Women (10-19)'
    
    name = col_name.replace("_Total", "").replace("_Male", "").replace("_Female", "").split("(")[0].strip()
    if "_" in name: name = name.split("_")[0]
    return name

def get_maternal_denominator(col_name, age_filter, all_cols):
    clean_name = get_clean_indicator_name(col_name)
    suffix = age_filter
    
    denom_col = None
    if clean_name == "2. Delivered with at least 4 ANC visits":
        denom_col = f"Total Deliveries_{suffix}"
    elif clean_name == "9. Delivered & completed at least 8ANC (a+b)":
        denom_col = f"Women who delivered and were tracked during pregnancy  (a+b)-c_{suffix}"
        
    elif clean_name == "2. Completed at least 2 PP check-ups":
        denom_col = f"Total Deliveries_{suffix}"
    elif clean_name == "9. Women gave birth completed at least 4PNC =(a+b)":
        denom_col = f"PP Women who were tracked during pregnancy =(a+b)-c_{suffix}"
        
    elif clean_name in ["10. PP women who completed iron with folic acid", "11. PP women given Vitamin A supplementation"]:
        denom_col = "Elig. Pop."
        
    # --- Nutritional & Td Denominators ---
    elif clean_name in [
        '1. Assessed Nutritional Status (Normal BMI)',
        '1. Assessed Nutritional Status (Low BMI)',
        '1. Assessed Nutritional Status (High BMI)',
        '1. Assessed Nutritional Status',
        '2. Given at least 2 doses of Td (1st time)',
        '3. Given at least 3 doses of Td (2nd+ time)',
        '4. Completed Iron w/ Folic Acid'
    ]:
        denom_col = "Elig. Pop."
        
    # --- New Template Denominators ---
    elif clean_name == "2. Tested Positive for Syphilis":
        denom_col = f"Pregnant women screened for syphilis_{suffix}"
    elif clean_name == "4. Screened Reactive to Hepatitis B":
        denom_col = f"Pregnant Women screened for Hepatitis B_{suffix}"
    elif clean_name == "6. Screened Reactive to HIV":
        denom_col = f"Pregnant Women Screened for HIV_{suffix}"
    elif clean_name == "2. Diagnosed with Anemia":
        denom_col = f"Pregnant women tested for CBC/Hgb/Hct_{suffix}"
    elif clean_name == "4. Tested Positive for Gestational Diabetes":
        denom_col = f"Pregnant women screened for gestational diabetes_{suffix}"
    elif clean_name == "1. Adolescent Women (10-14)":
        denom_col = "Pop. (10-14 years old Women)_Total"
    elif clean_name == "2. Adolescent Women (15-19)":
        denom_col = "Pop. (15-19 years old Women)_Total"
    elif clean_name == "3. Adolescent Women (10-19)":
        denom_col = "Pop. (10-19 years old Women)_Total"
        
    if denom_col and denom_col in all_cols:
        return denom_col
    elif denom_col:
        clean_target = denom_col.replace("  ", " ").replace("=", "").strip().lower()
        for c in all_cols:
            if clean_target in c.replace("  ", " ").replace("=", "").strip().lower():
                return c
                
    return "Elig. Pop." if "Elig. Pop." in all_cols else None

# --- UI RENDERERS ---
def render_footer():
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #888888; padding: 10px;'>
            <p>Developed by <strong>JangTV</strong></p>
            <img src="https://github.com/RJA24/abra-sbi-dashboard/blob/main/357094382_2458785624282603_4372984338912374777_n.png?raw=true" width="80" style="margin-top: -10px; opacity: 0.8;">
        </div>
        """, 
        unsafe_allow_html=True
    )
def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender, year, filter_rhus):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        filtered_df = filter_data(raw_df, start_m, end_m, gender, year)
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
            
        safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
        elig_cols = [c for c in filtered_df.columns if 'elig' in c.lower() or 'pop' in c.lower()]
        
        cols_to_plot = []
        for base in base_metrics:
            for col in filtered_df.columns:
                if base.lower() in col.lower() and col not in ['Area', 'Month', 'Year'] and col not in elig_cols:
                    if "%" not in col and "deficit" not in col.lower() and "previous" not in col.lower():
                        if col not in cols_to_plot:  cols_to_plot.append(col)
        
        if cols_to_plot:
            agg_dict = {col: 'sum' for col in cols_to_plot}
            for ec in elig_cols: agg_dict[ec] = 'max' 
                
            agg_df = filtered_df.groupby('Area').agg(agg_dict).reset_index()
            view_mode = st.radio("📊 Select Display Metric", ["Raw Counts", "Percentage (%) Coverage"], horizontal=True, key=f"toggle_view_{safe_filename}_{year}_{gender}")
            
            default_cols = []
            for c in cols_to_plot:
                c_base = c.replace(f"_{gender}", "").strip()
                is_parent = False
                for other_c in cols_to_plot:
                    if other_c != c:
                        other_base = other_c.replace(f"_{gender}", "").strip()
                        if other_base.startswith(c_base + " ") or other_base.startswith(c_base + "("):
                            is_parent = True; break
                if not is_parent: default_cols.append(c)
            if not default_cols and len(cols_to_plot) > 0: default_cols = [cols_to_plot[0]]
            
            with st.expander("⚙️ Add / Remove Indicators"):
                selected_cols = st.multiselect("Select specific indicators to include in the dashboard:", options=cols_to_plot, default=default_cols, key=f"ms_picker_{safe_filename}_{year}_{gender}", label_visibility="collapsed")

            valid_selected = [c for c in selected_cols if c in agg_df.columns]
            uid = f"imm_{safe_filename}_{year}_{gender}"
            
            if valid_selected:
                provincial_antigens = {col: agg_df[col].sum() for col in valid_selected}
                provincial_elig = sum([agg_df[ec].sum() for ec in elig_cols[:1]]) if elig_cols else 1
                
                st.markdown(f"#### 🏆 Summary ({location_header.replace('📍 ', '')})")
                
                # CHUNK CARDS INTO A GRID (Max 4 per row)
                cols_per_row = 4
                rows = [st.columns(cols_per_row) for _ in range((len(valid_selected) + cols_per_row - 1) // cols_per_row)]
                
                for i, col in enumerate(valid_selected):
                    row_idx = i // cols_per_row
                    col_idx = i % cols_per_row
                    
                    total_val = provincial_antigens[col]
                    clean_name = col.replace(f"_{gender}", "")
                    
                    if view_mode == "Percentage (%) Coverage" and elig_cols:
                        perc = (total_val / provincial_elig) * 100 if provincial_elig > 0 else 0
                        rows[row_idx][col_idx].metric(label=f"{clean_name} Target", value=f"{perc:.1f}%")
                    else:
                        rows[row_idx][col_idx].metric(label=f"{clean_name}", value=f"{int(total_val):,}")
                
                st.markdown("---")
                chart_df = agg_df[['Area'] + valid_selected + elig_cols].copy()
                abra_total_df = pd.DataFrame()
                abra_total_df['Vaccine/Antigen'] = valid_selected
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    main_elig_col = elig_cols[0]
                    for col in valid_selected:
                        chart_df[col] = np.where(chart_df[main_elig_col] > 0, (chart_df[col] / chart_df[main_elig_col]) * 100, 0)
                        chart_df[col] = chart_df[col].round(1)
                    prov_counts = [provincial_antigens[c] for c in valid_selected]
                    abra_total_df['Count'] = [(c / provincial_elig * 100) if provincial_elig > 0 else 0 for c in prov_counts]
                    abra_total_df['Count'] = abra_total_df['Count'].round(1)
                    y_axis_label = "Coverage (%)"
                else:
                    abra_total_df['Count'] = [provincial_antigens[c] for c in valid_selected]
                    y_axis_label = "Number of Children"

                st.markdown(f"#### 📈 {tab_title} - Aggregate Total")
                abra_total_df['Vaccine/Antigen'] = abra_total_df['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                
                fig_abra = px.bar(abra_total_df, x='Vaccine/Antigen', y='Count', color='Vaccine/Antigen', title=f"Aggregate Total ({start_m} - {end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel)
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    fig_abra.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                fig_abra.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_abra.update_layout(xaxis_title="Antigen", yaxis_title=y_axis_label, showlegend=False, margin=dict(t=60))
                st.plotly_chart(fig_abra, use_container_width=True, key=f"abra_{uid}")

                is_single_rhu = filter_rhus and "Abra (Total)" not in filter_rhus and len(filter_rhus) == 1
                
                if not is_single_rhu:
                    st.markdown("---")
                    st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                    
                    if len(valid_selected) == 1:
                        sort_order = st.radio("Sort RHUs by:", ["Alphabetical", "Highest to Lowest"], horizontal=True, key=f"sort_rhu_{uid}")
                        if sort_order == "Highest to Lowest":
                            chart_df = chart_df.sort_values(by=valid_selected[0], ascending=False)
                        else:
                            chart_df = chart_df.sort_values(by='Area', ascending=True)
                    else:
                        chart_df = chart_df.sort_values(by='Area', ascending=True)

                    melted = chart_df.melt(id_vars='Area', value_vars=valid_selected, var_name='Vaccine/Antigen', value_name='Count')
                    melted['Vaccine/Antigen'] = melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                    
                    fig_rhu = px.bar(melted, x='Area', y='Count', color='Vaccine/Antigen', barmode='group', title=f"Breakdown ({start_m} - {end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel, category_orders={"Area": chart_df['Area'].tolist()})
                    if view_mode == "Percentage (%) Coverage" and elig_cols:
                        fig_rhu.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                    fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                    fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title=y_axis_label, legend_title="Antigen", margin=dict(t=60))
                    st.plotly_chart(fig_rhu, use_container_width=True, key=f"rhu_{uid}")
                    
                    st.markdown("---")
                    st.markdown(f"#### 🏆 Top Performing RHUs (Average)")
                    top5_df = chart_df.copy()
                    top5_df['Rank_Metric'] = top5_df[valid_selected].mean(axis=1)
                    top5_df = top5_df.sort_values(by='Rank_Metric', ascending=True).tail(5)
                    fig_top5 = px.bar(top5_df, x='Rank_Metric', y='Area', orientation='h', title=f"Top RHUs ({start_m} - {end_m})", text_auto='.1f' if view_mode == "Percentage (%) Coverage" else True, color='Rank_Metric', color_continuous_scale="Greens")
                    fig_top5.update_layout(xaxis_title=y_axis_label, yaxis_title="Rural Health Unit (RHU)", showlegend=False, margin=dict(t=60))
                    st.plotly_chart(fig_top5, use_container_width=True, key=f"top5_{uid}")
                    
                    st.markdown("---")
                    st.markdown(f"#### 🗺️ Heatmap")
                    map_df = chart_df.copy()
                    map_df['Rank_Metric'] = map_df[valid_selected].mean(axis=1)
                    map_df['Lat'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[0])
                    map_df['Lon'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[1])
                    map_df = map_df[map_df['Lat'] != 0] 
                    color_scale = "RdYlGn" if view_mode == "Percentage (%) Coverage" else "Blues"
                    map_title = f"Geospatial View: Average {y_axis_label}"
                    fig_map = px.scatter_mapbox(map_df, lat="Lat", lon="Lon", hover_name="Area", hover_data={"Lat": False, "Lon": False, "Rank_Metric": ':.1f'}, color="Rank_Metric", size="Rank_Metric", color_continuous_scale=color_scale, size_max=20, zoom=8.5, center={"lat": 17.55, "lon": 120.75}, mapbox_style="carto-positron", title=map_title)
                    fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                    st.plotly_chart(fig_map, use_container_width=True, key=f"map_{uid}")
                
                st.markdown("---")
                st.markdown(f"#### 📉 Monthly Trend Analysis")
                trend_agg = filtered_df.groupby('Month')[valid_selected].sum().reset_index()
                months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                trend_agg['Month'] = pd.Categorical(trend_agg['Month'], categories=months_order, ordered=True)
                trend_agg = trend_agg.sort_values('Month')
                trend_chart_df = pd.DataFrame({'Month': trend_agg['Month']})
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    for col in valid_selected:
                        trend_chart_df[col] = [(v / provincial_elig * 100) if provincial_elig > 0 else 0 for v in trend_agg[col]]
                        trend_chart_df[col] = trend_chart_df[col].round(1)
                    y_trend_label = "Coverage (%)"
                else:
                    for col in valid_selected: trend_chart_df[col] = trend_agg[col]
                    y_trend_label = "Number of Children"
                trend_melted = trend_chart_df.melt(id_vars='Month', value_vars=valid_selected, var_name='Vaccine/Antigen', value_name='Count')
                trend_melted['Vaccine/Antigen'] = trend_melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                fig_trend = px.line(trend_melted, x='Month', y='Count', color='Vaccine/Antigen', markers=True, title=f"Trend ({start_m} - {end_m})", color_discrete_sequence=px.colors.qualitative.Pastel)
                if view_mode == "Percentage (%) Coverage" and elig_cols: fig_trend.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                fig_trend.update_layout(xaxis_title="Month", yaxis_title=y_trend_label, legend_title="Antigen", margin=dict(t=40), hovermode="x unified")
                st.plotly_chart(fig_trend, use_container_width=True, key=f"trend_{uid}")
                
                dose_1_col = next((c for c in valid_selected if " 1" in c or "1_" in c), None)
                dose_last_col = next((c for c in valid_selected if " 3" in c or "3_" in c), next((c for c in valid_selected if " 2" in c and ("MMR" in c.upper() or "MCV" in c.upper())), None))
                
                if dose_1_col and dose_last_col and tab_title != "Birth Doses":
                    st.markdown("---")
                    st.markdown(f"#### ⚠️ Dropout Analysis ({dose_1_col.replace(f'_{gender}', '')} to {dose_last_col.replace(f'_{gender}', '')})")
                    drop_df = agg_df[['Area', dose_1_col, dose_last_col]].copy()
                    drop_df['Dropout Rate (%)'] = np.where(drop_df[dose_1_col] > 0, ((drop_df[dose_1_col] - drop_df[dose_last_col]) / drop_df[dose_1_col]) * 100, 0)
                    drop_df['Dropout Rate (%)'] = drop_df['Dropout Rate (%)'].round(1)
                    fig_drop = px.bar(drop_df, x='Area', y='Dropout Rate (%)', text_auto=True, color='Dropout Rate (%)', color_continuous_scale=["lightgreen", "yellow", "red"], title="Highlighting RHUs with high dropout rates from first to final dose.")
                    fig_drop.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Warning Threshold (10%)")
                    fig_drop.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Dropout Rate (%)", margin=dict(t=40))
                    st.plotly_chart(fig_drop, use_container_width=True, key=f"drop_{uid}")

            else:
                st.info("👆 Please select at least one indicator from the dropdown above to view the charts.")
            
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View & Download Filtered Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_Data_{start_m}_to_{end_m}.csv", mime="text/csv")
    else:
        st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")
        
def render_ncd_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender, year, filter_rhus):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        
        valid_year_cols = ['Area', 'Month', 'Year']
        for col in year_df.columns:
            if col not in valid_year_cols:
                if 'elig' in col.lower() or 'pop' in col.lower():
                    valid_year_cols.append(col)
                elif pd.api.types.is_numeric_dtype(year_df[col]):
                    if year_df[col].sum() > 0:
                        valid_year_cols.append(col)
        
        filtered_df = filter_ncd_data(raw_df, start_m, end_m, gender, year, is_cancer=False)
        
        cols_to_keep_final = [c for c in filtered_df.columns if c in valid_year_cols]
        filtered_df = filtered_df[cols_to_keep_final]
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
        elig_cols = [c for c in filtered_df.columns if 'elig' in c.lower() or 'pop' in c.lower()]
        
        cols_to_plot = []
        for base in base_metrics:
            group_cols = []
            for col in filtered_df.columns:
                clean_col_name = col.replace('\n', ' ')
                if base.lower() in clean_col_name.lower() and col not in ['Area', 'Month', 'Year'] and col not in elig_cols:
                    if "%" not in col and "deficit" not in clean_col_name.lower() and "previous" not in clean_col_name.lower():
                        group_cols.append(col)
            
            if group_cols:
                total_cols = [c for c in group_cols if "total" in c.lower()]
                if total_cols: 
                    if total_cols[0] not in cols_to_plot: cols_to_plot.append(total_cols[0])
                else: 
                    best_col = max(group_cols, key=lambda c: pd.to_numeric(filtered_df[c], errors='coerce').sum())
                    if best_col not in cols_to_plot: cols_to_plot.append(best_col)
        
        if cols_to_plot:
            agg_dict = {col: 'sum' for col in cols_to_plot}
            for ec in elig_cols: agg_dict[ec] = 'max' 
                
            agg_df = filtered_df.groupby('Area').agg(agg_dict).reset_index()
            uid = f"ncd_{safe_filename}_{year}_{gender}"
            
            with st.expander("⚙️ Add / Remove NCD Indicators"):
                selected_cols = st.multiselect("Select indicators to include in the charts:", options=cols_to_plot, default=cols_to_plot, key=f"ms_ncd_{safe_filename}_{year}_{gender}", format_func=get_clean_indicator_name)

            valid_selected = [c for c in selected_cols if c in agg_df.columns]

            if valid_selected:
                provincial_antigens = {col: agg_df[col].sum() for col in valid_selected}
                
                c_assessed = next((c for c in valid_selected if "risk assessed" in c.lower()), None)
                c_hyper = next((c for c in valid_selected if "hypertensive" in c.lower()), None)
                c_dm = next((c for c in valid_selected if "type 2 dm" in c.lower() or "diabetes" in c.lower()), None)
                lifestyle_cols = [c for c in valid_selected if c not in [c_assessed, c_hyper, c_dm] and c not in elig_cols]
                
                st.markdown(f"#### 🏆 Summary ({location_header.replace('📍 ', '')})")
                
                cols_per_row = 5
                rows = [st.columns(cols_per_row) for _ in range((len(valid_selected) + cols_per_row - 1) // cols_per_row)]
                
                for i, col in enumerate(valid_selected):
                    row_idx = i // cols_per_row
                    col_idx = i % cols_per_row
                    total_val = provincial_antigens[col]
                    short_name = get_clean_indicator_name(col)
                    
                    if c_assessed and col in [c_hyper, c_dm] and provincial_antigens[c_assessed] > 0:
                        yield_pct = (total_val / provincial_antigens[c_assessed]) * 100
                        rows[row_idx][col_idx].metric(label=short_name, value=f"{int(total_val):,}", delta=f"{yield_pct:.1f}% Screening Yield", delta_color="off")
                    else:
                        rows[row_idx][col_idx].metric(label=short_name, value=f"{int(total_val):,}")
                
                st.markdown("---")
                
                if c_assessed or lifestyle_cols:
                    st.markdown(f"#### 🧬 {tab_title} : Health Footprint")
                    v_col1, v_col2 = st.columns(2)
                    
                    with v_col1:
                        if lifestyle_cols:
                            radar_data = pd.DataFrame({
                                'Risk Factor': [get_clean_indicator_name(c) for c in lifestyle_cols],
                                'Count': [provincial_antigens[c] for c in lifestyle_cols]
                            })
                            fig_radar = px.line_polar(radar_data, r='Count', theta='Risk Factor', line_close=True, title="🕸️ Lifestyle Risk Profile (Radar)", markers=True, color_discrete_sequence=["#FF9933"])
                            fig_radar.update_traces(fill='toself')
                            st.plotly_chart(fig_radar, use_container_width=True, key=f"radar_{uid}")
                        else:
                            st.info("Select lifestyle indicators (Smoking, Alcohol, etc.) to view the Risk Profile.")
                            
                    with v_col2:
                        if c_assessed and (c_hyper or c_dm):
                            bar_stages = ["Total Risk Assessed"]
                            bar_counts = [provincial_antigens[c_assessed]]
                            if c_hyper: 
                                bar_stages.append("Hypertensive")
                                bar_counts.append(provincial_antigens[c_hyper])
                            if c_dm:
                                bar_stages.append("Type 2 DM")
                                bar_counts.append(provincial_antigens[c_dm])
                                
                            diag_df = pd.DataFrame({'Condition': bar_stages, 'Patients': bar_counts})
                            fig_diag = px.bar(diag_df, x='Condition', y='Patients', title="📊 Assessment vs. Diagnosed Yield", color='Condition', text_auto=True, color_discrete_sequence=["#3366CC", "#DC3912", "#FF9900"])
                            fig_diag.update_traces(textposition="outside", cliponaxis=False)
                            fig_diag.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total Patients", margin=dict(t=40))
                            st.plotly_chart(fig_diag, use_container_width=True, key=f"diag_bar_{uid}")
                        else:
                            st.info("Select 'Risk Assessed' and at least one disease (Hypertension/DM) to view the Diagnostic Yield.")
                
                st.markdown("---")
                st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                
                chart_df = agg_df[['Area'] + valid_selected].copy()
                
                if len(valid_selected) == 1:
                    sort_order = st.radio("Sort RHUs by:", ["Alphabetical", "Highest to Lowest"], horizontal=True, key=f"sort_rhu_{uid}")
                    if sort_order == "Highest to Lowest":
                        chart_df = chart_df.sort_values(by=valid_selected[0], ascending=False)
                    else:
                        chart_df = chart_df.sort_values(by='Area', ascending=True)
                else:
                    chart_df = chart_df.sort_values(by='Area', ascending=True)
                
                melted = chart_df.melt(id_vars='Area', value_vars=valid_selected, var_name='Indicator_Raw', value_name='Count')
                melted['Indicator'] = melted['Indicator_Raw'].apply(get_clean_indicator_name)
                
                fig_rhu = px.bar(melted, x='Area', y='Count', color='Indicator', barmode='group', title=f"Breakdown ({start_m} - {end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Set2, category_orders={"Area": chart_df['Area'].tolist()})
                fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Count", legend_title="Indicator", margin=dict(t=60))
                st.plotly_chart(fig_rhu, use_container_width=True, key=f"rhu_{uid}")
                
            else:
                st.info("👆 Please select at least one indicator from the dropdown above to view the charts.")
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View & Download Raw NCD Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_NCD_{safe_filename}_Data.csv", mime="text/csv")
    else:
        st.info("No NCD data uploaded yet. Please go to the Data Uploader page to add your files.")

def render_mortality_tab(tab_title, df_key, base_metrics, start_m, end_m, gender, year, filter_rhus, chart_type="bar"):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        
        valid_year_cols = ['Area', 'Month', 'Year']
        for col in year_df.columns:
            if col not in valid_year_cols:
                if 'elig' in col.lower() or 'pop' in col.lower():
                    valid_year_cols.append(col)
                elif pd.api.types.is_numeric_dtype(year_df[col]):
                    if year_df[col].sum() > 0:
                        valid_year_cols.append(col)
        
        filtered_df = filter_ncd_data(raw_df, start_m, end_m, gender, year, is_cancer=False)
        
        cols_to_keep_final = [c for c in filtered_df.columns if c in valid_year_cols]
        filtered_df = filtered_df[cols_to_keep_final]
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
        elig_cols = [c for c in filtered_df.columns if 'elig' in c.lower() or 'pop' in c.lower()]
        
        cols_to_plot = []
        for base in base_metrics:
            for col in filtered_df.columns:
                clean_col_name = col.replace('\n', ' ')
                if base.lower() in clean_col_name.lower() and col not in ['Area', 'Month', 'Year'] and col not in elig_cols:
                    if col not in cols_to_plot: cols_to_plot.append(col)
        
        if cols_to_plot:
            agg_dict = {col: 'sum' for col in cols_to_plot}
            for ec in elig_cols: agg_dict[ec] = 'max' 
            agg_df = filtered_df.groupby('Area').agg(agg_dict).reset_index()
            uid = f"mort_{safe_filename}_{year}_{gender}"
            
            with st.expander("⚙️ Add / Remove Indicators"):
                selected_cols = st.multiselect("Select indicators to include in the charts:", options=cols_to_plot, default=cols_to_plot, key=f"ms_mort_{safe_filename}_{year}_{gender}", format_func=get_clean_indicator_name)

            valid_selected = [c for c in selected_cols if c in agg_df.columns]

            if valid_selected:
                view_mode = "Raw Counts"
                if elig_cols:
                    view_mode = st.radio("📊 Select Display Metric", ["Raw Counts", "Percentage (%)"], horizontal=True, key=f"toggle_view_mort_{safe_filename}_{year}_{gender}")
                    
                provincial_antigens = {col: agg_df[col].sum() for col in valid_selected}
                provincial_elig = sum([agg_df[ec].sum() for ec in elig_cols[:1]]) if elig_cols else 1
                
                st.markdown(f"#### 🏆 Summary ({location_header.replace('📍 ', '')})")
                cols_per_row = 5
                rows = [st.columns(cols_per_row) for _ in range((len(valid_selected) + cols_per_row - 1) // cols_per_row)]
                
                for i, col in enumerate(valid_selected):
                    row_idx = i // cols_per_row
                    col_idx = i % cols_per_row
                    total_val = provincial_antigens[col]
                    short_name = get_clean_indicator_name(col)
                    
                    if view_mode == "Percentage (%)" and elig_cols:
                        perc = (total_val / provincial_elig) * 100 if provincial_elig > 0 else 0
                        rows[row_idx][col_idx].metric(label=f"{short_name} (%)", value=f"{perc:.3f}%")
                    else:
                        rows[row_idx][col_idx].metric(label=short_name, value=f"{int(total_val):,}")

                if "Premature NCD" in tab_title:
                    disease_cols = [c for c in valid_selected if "total" not in c.lower() and "pop" not in c.lower()]
                    if disease_cols:
                        donut_data = pd.DataFrame({
                            'Cause': [get_clean_indicator_name(c) for c in disease_cols],
                            'Deaths': [provincial_antigens[c] for c in disease_cols]
                        })
                        donut_data = donut_data[donut_data['Deaths'] > 0] 
                        if not donut_data.empty:
                            st.markdown("<br>", unsafe_allow_html=True)
                            fig_donut = px.pie(donut_data, values='Deaths', names='Cause', hole=0.4, title="🍩 Cause of Death Breakdown", color_discrete_sequence=px.colors.qualitative.Pastel)
                            fig_donut.update_traces(textposition='inside', textinfo='percent+label')
                            fig_donut.update_layout(margin=dict(t=40, b=0))
                            st.plotly_chart(fig_donut, use_container_width=True, key=f"donut_{uid}")
                
                st.markdown("---")
                st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                
                chart_df = agg_df[['Area'] + valid_selected + elig_cols].copy()
                y_axis_label = "Reported Cases"
                
                if view_mode == "Percentage (%)" and elig_cols:
                    main_elig_col = elig_cols[0]
                    for col in valid_selected:
                        chart_df[col] = np.where(chart_df[main_elig_col] > 0, (chart_df[col] / chart_df[main_elig_col]) * 100, 0)
                        chart_df[col] = chart_df[col].round(3)
                    y_axis_label = "Mortality Rate (%)"
                
                if len(valid_selected) == 1:
                    sort_order = st.radio("Sort RHUs by:", ["Alphabetical", "Highest to Lowest"], horizontal=True, key=f"sort_rhu_{uid}")
                    if sort_order == "Highest to Lowest":
                        chart_df = chart_df.sort_values(by=valid_selected[0], ascending=False)
                    else:
                        chart_df = chart_df.sort_values(by='Area', ascending=True)
                else:
                    chart_df = chart_df.sort_values(by='Area', ascending=True)

                melted = chart_df.melt(id_vars='Area', value_vars=valid_selected, var_name='Indicator_Raw', value_name='Count')
                melted['Indicator'] = melted['Indicator_Raw'].apply(get_clean_indicator_name)
                
                if chart_type == "line":
                    fig_rhu = px.line(melted, x='Area', y='Count', color='Indicator', markers=True, title=f"Breakdown ({start_m} - {end_m})", color_discrete_sequence=px.colors.qualitative.Set1, category_orders={"Area": chart_df['Area'].tolist()})
                else:
                    fig_rhu = px.bar(melted, x='Area', y='Count', color='Indicator', barmode='group', title=f"Breakdown ({start_m} - {end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Set1, category_orders={"Area": chart_df['Area'].tolist()})
                    fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                    
                fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title=y_axis_label, legend_title="Indicator", margin=dict(t=60))
                st.plotly_chart(fig_rhu, use_container_width=True, key=f"rhu_{uid}")

                st.markdown("---")
                st.markdown("#### 🚨 High-Risk Hotspots & Leaderboard")
                col_m1, col_m2 = st.columns(2)
                
                primary_col = valid_selected[0]
                metric_name = get_clean_indicator_name(primary_col)
                
                with col_m1:
                    st.markdown(f"**Top RHUs (Highest {metric_name})**")
                    leader_df = chart_df.copy()
                    leader_df = leader_df.sort_values(by=primary_col, ascending=True).tail(5)
                    fig_lead = px.bar(leader_df, x=primary_col, y='Area', orientation='h', text_auto=True if view_mode == "Raw Counts" else '.3f', color=primary_col, color_continuous_scale="Reds")
                    fig_lead.update_layout(xaxis_title=y_axis_label, yaxis_title="", margin=dict(t=0, b=0))
                    st.plotly_chart(fig_lead, use_container_width=True, key=f"lead_{uid}")
                    
                with col_m2:
                    st.markdown(f"**Geospatial Hotspots ({metric_name})**")
                    map_df = chart_df.copy()
                    map_df['Lat'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[0])
                    map_df['Lon'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[1])
                    map_df = map_df[map_df['Lat'] != 0] 
                    
                    fig_map = px.scatter_mapbox(map_df, lat="Lat", lon="Lon", hover_name="Area", 
                                                hover_data={"Lat": False, "Lon": False, primary_col: True if view_mode == "Raw Counts" else ':.3f'}, 
                                                color=primary_col, size=primary_col, 
                                                color_continuous_scale="Reds", size_max=20, zoom=8.5, 
                                                center={"lat": 17.595, "lon": 120.613}, mapbox_style="carto-positron")
                    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                    st.plotly_chart(fig_map, use_container_width=True, key=f"map_hotspot_{uid}")
                
                if len(filtered_df['Month'].unique()) > 1:
                    st.markdown("---")
                    st.markdown(f"#### 📈 Monthly Trend")
                    trend_agg_dict = {col: 'sum' for col in valid_selected}
                    for ec in elig_cols: trend_agg_dict[ec] = 'max'
                    trend_agg = filtered_df.groupby('Month').agg(trend_agg_dict).reset_index()

                    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    trend_agg['Month'] = pd.Categorical(trend_agg['Month'], categories=months_order, ordered=True)
                    trend_agg = trend_agg.sort_values('Month').dropna()
                    
                    if view_mode == "Percentage (%)" and elig_cols:
                        for col in valid_selected:
                            trend_agg[col] = np.where(provincial_elig > 0, (trend_agg[col] / provincial_elig) * 100, 0).round(3)
                    
                    trend_melted = trend_agg.melt(id_vars='Month', value_vars=valid_selected, var_name='Indicator_Raw', value_name='Count')
                    trend_melted['Indicator'] = trend_melted['Indicator_Raw'].apply(get_clean_indicator_name)
                    
                    fig_trend = px.line(trend_melted, x='Month', y='Count', color='Indicator', markers=True, title=f"Trend ({start_m} - {end_m})", color_discrete_sequence=px.colors.qualitative.Set1)
                    fig_trend.update_layout(xaxis_title="Month", yaxis_title=y_axis_label, legend_title="Indicator", margin=dict(t=40))
                    st.plotly_chart(fig_trend, use_container_width=True, key=f"trend_{uid}")
                
            else:
                st.info("👆 Please select at least one indicator from the dropdown above to view the charts.")
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View & Download Raw Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_Data.csv", mime="text/csv")
    else:
        st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")

def render_cervical_cancer_tab(df_key, start_m, end_m, gender, year, filter_rhus):
    if gender == "Male":
        st.info("🎗️ Cervical Cancer screening data is exclusively tracked for the Female demographic. Please switch the Global Filter to 'Female' or 'Total'.")
        return
        
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        valid_year_cols = ['Area', 'Month', 'Year']
        for col in year_df.columns:
            if col not in valid_year_cols:
                if 'elig' in col.lower() or 'pop' in col.lower():
                    valid_year_cols.append(col)
                elif pd.api.types.is_numeric_dtype(year_df[col]):
                    if year_df[col].sum() > 0:
                        valid_year_cols.append(col)
        
        filtered_df = filter_ncd_data(raw_df, start_m, end_m, "Total", year, is_cancer=True)
        
        cols_to_keep_final = [c for c in filtered_df.columns if c in valid_year_cols]
        filtered_df = filtered_df[cols_to_keep_final]
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        c_scr_tot = get_ncd_col(filtered_df, ["screened", "total"], ["%", "suspicious", "positive", "linked", "treated", "referred", "suspect"])
        c_susp_no = get_ncd_col(filtered_df, ["suspicious", "no."], ["%", "linked", "treated", "referred", "total"])
        c_susp_link_tr = get_ncd_col(filtered_df, ["suspicious", "treated"], ["%"])
        c_susp_link_ref = get_ncd_col(filtered_df, ["suspicious", "referred"], ["%"])
        c_susp_link_tot = get_ncd_col(filtered_df, ["suspicious", "total", "linked"], ["%"])
        
        c_pos_tot = get_ncd_col(filtered_df, ["positive", "total"], ["%", "linked", "treated", "referred", "care", "suspect"])
        c_pos_link_tr = get_ncd_col(filtered_df, ["positive", "treated"], ["%"])
        c_pos_link_ref = get_ncd_col(filtered_df, ["positive", "referred"], ["%"])
        c_pos_link_tot = get_ncd_col(filtered_df, ["positive", "total", "linked"], ["%"])
        
        c_pos_suspect_tot = get_ncd_col(filtered_df, ["positive or suspect", "total"], ["%"])
        
        cols_to_agg = [c for c in [c_scr_tot, c_susp_no, c_susp_link_tr, c_susp_link_ref, c_susp_link_tot, c_pos_tot, c_pos_link_tr, c_pos_link_ref, c_pos_link_tot, c_pos_suspect_tot] if c]
        if not cols_to_agg:
            st.warning("Could not identify specific Cervical Cancer columns from the template. Ensure you are using the official DOH format.")
            return
            
        agg_df = filtered_df.groupby('Area')[cols_to_agg].sum().reset_index()
        is_2024 = c_pos_suspect_tot is not None
        
        if is_2024:
            st.info("📌 **2024 Legacy Format Detected:** Displaying simplified screening and suspect tracking.")
            st.markdown("### 🎗️ Cervical Cancer Screening (2024)")
            c1, c2 = st.columns(2)
            if c_scr_tot: c1.metric("Total Women Screened", f"{int(agg_df[c_scr_tot].sum()):,}")
            if c_pos_suspect_tot: c2.metric("Found Positive or Suspect", f"{int(agg_df[c_pos_suspect_tot].sum()):,}")
            
            if c_scr_tot:
                st.markdown("---")
                prov_tot = int(agg_df[c_scr_tot].sum())
                agg_df = agg_df.sort_values(by='Area', ascending=True)
                fig_scr = px.bar(agg_df, x='Area', y=c_scr_tot, title=f"Total Women Screened for Cervical Cancer (Total: {prov_tot:,})", text_auto=True, color_discrete_sequence=["#66B2FF"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_scr.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_scr.update_layout(xaxis_title="RHU", yaxis_title="Number of Women", margin=dict(t=50))
                st.plotly_chart(fig_scr, use_container_width=True, key=f"cerv_leg_1_{year}")
                
            if c_pos_suspect_tot:
                st.markdown("---")
                prov_tot = int(agg_df[c_pos_suspect_tot].sum())
                fig_pos = px.bar(agg_df, x='Area', y=c_pos_suspect_tot, title=f"Found Positive or Suspect (Total: {prov_tot:,})", text_auto=True, color_discrete_sequence=["#EF553B"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_pos.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_pos.update_layout(xaxis_title="RHU", yaxis_title="Number of Women", margin=dict(t=50))
                st.plotly_chart(fig_pos, use_container_width=True, key=f"cerv_leg_2_{year}")
                
            with st.expander("📄 View & Download Formatted Data"):
                st.dataframe(agg_df, use_container_width=True, hide_index=True)
            return

        st.markdown("### 🎗️ Cervical Cancer Screening & Linkage to Care")
        st.markdown(f"##### Medical Totals ({location_header.replace('📍 ', '')})")
        c1, c2, c3, c4, c5 = st.columns(5)
        if c_scr_tot: c1.metric("1. Total Screened", f"{int(agg_df[c_scr_tot].sum()):,}")
        if c_susp_no: c2.metric("2. Found Suspicious", f"{int(agg_df[c_susp_no].sum()):,}")
        if c_susp_link_tot: c3.metric("3. Suspicious & Linked", f"{int(agg_df[c_susp_link_tot].sum()):,}")
        if c_pos_tot: c4.metric("4. Found Positive", f"{int(agg_df[c_pos_tot].sum()):,}")
        if c_pos_link_tot: c5.metric("5. Positive & Linked", f"{int(agg_df[c_pos_link_tot].sum()):,}")
        
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("#### 🌪️ Screening Cascade (Suspicious)")
            susp_stages = ["Screened", "Suspicious", "Linked to Care"]
            susp_counts = [
                int(agg_df[c_scr_tot].sum()) if c_scr_tot else 0,
                int(agg_df[c_susp_no].sum()) if c_susp_no else 0,
                int(agg_df[c_susp_link_tot].sum()) if c_susp_link_tot else 0
            ]
            fig_f1 = px.funnel(pd.DataFrame({'Stage': susp_stages, 'Count': susp_counts}), x='Count', y='Stage', color_discrete_sequence=["#FFA15A"])
            st.plotly_chart(fig_f1, use_container_width=True, key=f"cerv_funnel_susp_{year}")
            
        with col_f2:
            st.markdown("#### 🌪️ Screening Cascade (Positive)")
            pos_stages = ["Screened", "Positive", "Linked to Care"]
            pos_counts = [
                int(agg_df[c_scr_tot].sum()) if c_scr_tot else 0,
                int(agg_df[c_pos_tot].sum()) if c_pos_tot else 0,
                int(agg_df[c_pos_link_tot].sum()) if c_pos_link_tot else 0
            ]
            fig_f2 = px.funnel(pd.DataFrame({'Stage': pos_stages, 'Count': pos_counts}), x='Count', y='Stage', color_discrete_sequence=["#EF553B"])
            st.plotly_chart(fig_f2, use_container_width=True, key=f"cerv_funnel_pos_{year}")

        st.markdown("---")
        st.markdown("#### 📊 RHU Breakdown: Screening Yield")
        cols_to_melt = [c for c in [c_scr_tot, c_susp_no, c_pos_tot] if c]
        if cols_to_melt:
            agg_df = agg_df.sort_values(by='Area', ascending=True)
            melted_rhu = agg_df[['Area'] + cols_to_melt].melt(id_vars='Area', var_name='Metric_Raw', value_name='Patients')
            clean_metric_names = {c_scr_tot: "Screened", c_susp_no: "Suspicious", c_pos_tot: "Positive"}
            melted_rhu['Metric'] = melted_rhu['Metric_Raw'].map(clean_metric_names)
            
            fig_rhu = px.bar(melted_rhu, x='Area', y='Patients', color='Metric', barmode='group', title="Screening Yield vs Abnormal Findings per RHU", text_auto=True, color_discrete_sequence=["#66B2FF", "#FFA15A", "#EF553B"], category_orders={"Area": agg_df['Area'].tolist()})
            fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
            fig_rhu.update_layout(xaxis_title="RHU", yaxis_title="Number of Women", margin=dict(t=50))
            st.plotly_chart(fig_rhu, use_container_width=True, key=f"cerv_rhu_bar_{year}")

        with st.expander("📄 View & Download Formatted Cervical Data"):
            clean_names = {
                c_scr_tot: "Screened (Total)", c_susp_no: "Suspicious (No.)", 
                c_susp_link_tr: "Suspicious Linked (Treated)", c_susp_link_ref: "Suspicious Linked (Referred)", c_susp_link_tot: "Suspicious Linked (Total)",
                c_pos_tot: "Positive (Total)", c_pos_link_tr: "Positive Linked (Treated)", 
                c_pos_link_ref: "Positive Linked (Referred)", c_pos_link_tot: "Positive Linked (Total)"
            }
            display_df = agg_df.rename(columns=clean_names)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(display_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_Cervical_Cancer_Data.csv", mime="text/csv")
    else:
        st.info("No Cervical Cancer data uploaded yet.")

def render_breast_cancer_tab(df_key, start_m, end_m, gender, year, filter_rhus):
    if gender == "Male":
        st.info("🎀 Breast Cancer screening data is exclusively tracked for the Female demographic. Please switch the Global Filter to 'Female' or 'Total'.")
        return
        
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        valid_year_cols = ['Area', 'Month', 'Year']
        for col in year_df.columns:
            if col not in valid_year_cols:
                if 'elig' in col.lower() or 'pop' in col.lower():
                    valid_year_cols.append(col)
                elif pd.api.types.is_numeric_dtype(year_df[col]):
                    if year_df[col].sum() > 0:
                        valid_year_cols.append(col)
        
        filtered_df = filter_ncd_data(raw_df, start_m, end_m, "Total", year, is_cancer=True)
        
        cols_to_keep_final = [c for c in filtered_df.columns if c in valid_year_cols]
        filtered_df = filtered_df[cols_to_keep_final]
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        b_leg_scr = get_ncd_col(filtered_df, ["screened for breast mass"], ["%", "suspicious"])
        b_leg_susp = get_ncd_col(filtered_df, ["suspicious breast mass"], ["%", "screened"])
        
        b_hr_scr_cbe = get_ncd_col(filtered_df, ["high risk", "detection", "cbe"], ["%"])
        b_hr_scr_mam = get_ncd_col(filtered_df, ["high risk", "detection", "mammogram"], ["%"])
        b_hr_scr_tot = get_ncd_col(filtered_df, ["high risk", "detection", "total"], ["%"])
        b_hr_rem_cbe = get_ncd_col(filtered_df, ["high risk", "remarkable", "cbe"], ["%", "linked"])
        b_hr_rem_mam = get_ncd_col(filtered_df, ["high risk", "remarkable", "mammogram"], ["%", "linked"])
        b_hr_rem_tot = get_ncd_col(filtered_df, ["high risk", "remarkable", "total"], ["%", "linked"])
        b_hr_link_cbe = get_ncd_col(filtered_df, ["high risk", "linked", "cbe"], ["%"])
        b_hr_link_mam = get_ncd_col(filtered_df, ["high risk", "linked", "mammogram"], ["%"])
        b_hr_link_tot = get_ncd_col(filtered_df, ["high risk", "linked", "total"], ["%"])
        
        b_as_scr_cbe = get_ncd_col(filtered_df, ["asymptomatic", "cbe"], ["%"])
        b_as_scr_mam = get_ncd_col(filtered_df, ["asymptomatic", "mammogram"], ["%"])
        b_as_scr_tot = get_ncd_col(filtered_df, ["asymptomatic", "total"], ["%"])
        b_as_rem_cbe = get_ncd_col(filtered_df, ["50-69", "remarkable", "cbe"], ["%", "high risk", "linked"])
        b_as_rem_mam = get_ncd_col(filtered_df, ["50-69", "remarkable", "mammogram"], ["%", "high risk", "linked"])
        b_as_rem_tot = get_ncd_col(filtered_df, ["50-69", "remarkable", "total"], ["%", "high risk", "linked"])
        b_as_link_cbe = get_ncd_col(filtered_df, ["50-69", "linked", "cbe"], ["%", "high risk"])
        b_as_link_mam = get_ncd_col(filtered_df, ["50-69", "linked", "mammogram"], ["%", "high risk"])
        b_as_link_tot = get_ncd_col(filtered_df, ["50-69", "linked", "total"], ["%", "high risk"])
        
        all_cols = [b_leg_scr, b_leg_susp, b_hr_scr_cbe, b_hr_scr_mam, b_hr_scr_tot, b_hr_rem_cbe, b_hr_rem_mam, b_hr_rem_tot, b_hr_link_cbe, b_hr_link_mam, b_hr_link_tot,
                    b_as_scr_cbe, b_as_scr_mam, b_as_scr_tot, b_as_rem_cbe, b_as_rem_mam, b_as_rem_tot, b_as_link_cbe, b_as_link_mam, b_as_link_tot]
        cols_to_agg = [c for c in all_cols if c]
        
        if not cols_to_agg:
            st.warning("Could not identify specific Breast Cancer columns from the template.")
            return
            
        agg_df = filtered_df.groupby('Area')[cols_to_agg].sum().reset_index()
        is_2024 = b_leg_scr is not None or b_leg_susp is not None
        
        if is_2024:
            st.info("📌 **2024 Legacy Format Detected:** Displaying simplified Breast Mass screening data.")
            st.markdown("### 🎀 Breast Cancer Screening (2024)")
            c1, c2 = st.columns(2)
            if b_leg_scr: c1.metric("Screened for Breast Mass", f"{int(agg_df[b_leg_scr].sum()):,}")
            if b_leg_susp: c2.metric("With Suspicious Breast Mass", f"{int(agg_df[b_leg_susp].sum()):,}")
            
            if b_leg_scr:
                st.markdown("---")
                prov_tot = int(agg_df[b_leg_scr].sum())
                agg_df = agg_df.sort_values(by='Area', ascending=True)
                fig_scr = px.bar(agg_df, x='Area', y=b_leg_scr, title=f"Screened for Breast Mass (Total: {prov_tot:,})", text_auto=True, color_discrete_sequence=["#FF99CC"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_scr.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_scr.update_layout(xaxis_title="RHU", yaxis_title="Number of Women", margin=dict(t=50))
                st.plotly_chart(fig_scr, use_container_width=True, key=f"br_leg_1_{year}")
                
            if b_leg_susp:
                st.markdown("---")
                prov_tot = int(agg_df[b_leg_susp].sum())
                fig_susp = px.bar(agg_df, x='Area', y=b_leg_susp, title=f"With Suspicious Breast Mass (Total: {prov_tot:,})", text_auto=True, color_discrete_sequence=["#EF553B"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_susp.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_susp.update_layout(xaxis_title="RHU", yaxis_title="Number of Women", margin=dict(t=50))
                st.plotly_chart(fig_susp, use_container_width=True, key=f"br_leg_2_{year}")
                
            with st.expander("📄 View & Download Formatted Data"):
                st.dataframe(agg_df, use_container_width=True, hide_index=True)
            return

        st.markdown(f"### 🎀 High Risk Women (30-69 y.o.) | {location_header.replace('📍 ', '')}")
        hr_c1, hr_c2, hr_c3 = st.columns(3)
        if b_hr_scr_tot: hr_c1.metric("1. Screened (Total)", f"{int(agg_df[b_hr_scr_tot].sum()):,}")
        if b_hr_rem_tot: hr_c2.metric("2. Found Remarkable (Total)", f"{int(agg_df[b_hr_rem_tot].sum()):,}")
        if b_hr_link_tot: hr_c3.metric("3. Linked to Care (Total)", f"{int(agg_df[b_hr_link_tot].sum()):,}")
        
        st.markdown("---")
        hr_col1, hr_col2 = st.columns([1, 2])
        
        with hr_col1:
            st.markdown("#### 🌪️ Care Pipeline")
            hr_funnel = pd.DataFrame({
                'Stage': ['Screened', 'Remarkable', 'Linked'],
                'Count': [
                    agg_df[b_hr_scr_tot].sum() if b_hr_scr_tot else 0,
                    agg_df[b_hr_rem_tot].sum() if b_hr_rem_tot else 0,
                    agg_df[b_hr_link_tot].sum() if b_hr_link_tot else 0
                ]
            })
            fig_hr_funnel = px.funnel(hr_funnel, x='Count', y='Stage', color_discrete_sequence=["#FF99CC"])
            st.plotly_chart(fig_hr_funnel, use_container_width=True, key=f"br_hr_funnel_{year}")

        with hr_col2:
            st.markdown("#### 📊 RHU Screening Breakdown (Stacked)")
            as_scr_cols = [c for c in [b_hr_scr_cbe, b_hr_scr_mam] if c] 
            if as_scr_cols:
                agg_df = agg_df.sort_values(by='Area', ascending=True)
                m = agg_df[['Area'] + as_scr_cols].melt(id_vars='Area')
                m['variable'] = m['variable'].apply(lambda x: "CBE" if x == b_hr_scr_cbe else "Mammogram")
                fig_hr_bar = px.bar(m, x='Area', y='value', color='variable', barmode='stack', title="Screenings by Methodology", text_auto=True, color_discrete_sequence=["#FF99CC", "#99CCFF"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_hr_bar.update_layout(xaxis_title="RHU", yaxis_title="Patients", margin=dict(t=30))
                st.plotly_chart(fig_hr_bar, use_container_width=True, key=f"breast_hr_bar_{year}")

        st.markdown("<br><br>", unsafe_allow_html=True)
        
        st.markdown("### 🎗️ Asymptomatic Women (50-69 y.o.)")
        as_c1, as_c2, as_c3 = st.columns(3)
        if b_as_scr_tot: as_c1.metric("1. Screened (Total)", f"{int(agg_df[b_as_scr_tot].sum()):,}")
        if b_as_rem_tot: as_c2.metric("2. Found Remarkable (Total)", f"{int(agg_df[b_as_rem_tot].sum()):,}")
        if b_as_link_tot: as_c3.metric("3. Linked to Care (Total)", f"{int(agg_df[b_as_link_tot].sum()):,}")
        
        st.markdown("---")
        as_col1, as_col2 = st.columns([1, 2])
        
        with as_col1:
            st.markdown("#### 🌪️ Care Pipeline")
            as_funnel = pd.DataFrame({
                'Stage': ['Screened', 'Remarkable', 'Linked'],
                'Count': [
                    agg_df[b_as_scr_tot].sum() if b_as_scr_tot else 0,
                    agg_df[b_as_rem_tot].sum() if b_as_rem_tot else 0,
                    agg_df[b_as_link_tot].sum() if b_as_link_tot else 0
                ]
            })
            fig_as_funnel = px.funnel(as_funnel, x='Count', y='Stage', color_discrete_sequence=["#66B2FF"])
            st.plotly_chart(fig_as_funnel, use_container_width=True, key=f"br_as_funnel_{year}")

        with as_col2:
            st.markdown("#### 📊 RHU Screening Breakdown (Stacked)")
            as_scr_cols = [c for c in [b_as_scr_cbe, b_as_scr_mam] if c] 
            if as_scr_cols:
                agg_df = agg_df.sort_values(by='Area', ascending=True)
                m = agg_df[['Area'] + as_scr_cols].melt(id_vars='Area')
                m['variable'] = m['variable'].apply(lambda x: "CBE" if x == b_as_scr_cbe else "Mammogram")
                fig_as_bar = px.bar(m, x='Area', y='value', color='variable', barmode='stack', title="Screenings by Methodology", text_auto=True, color_discrete_sequence=["#FF99CC", "#99CCFF"], category_orders={"Area": agg_df['Area'].tolist()})
                fig_as_bar.update_layout(xaxis_title="RHU", yaxis_title="Patients", margin=dict(t=30))
                st.plotly_chart(fig_as_bar, use_container_width=True, key=f"breast_as_bar_{year}")

        with st.expander("📄 View & Download Formatted Breast Cancer Data (RHU Breakdown)"):
            clean_names = {
                b_hr_scr_cbe: "HR Screened (CBE)", b_hr_scr_mam: "HR Screened (Mammo)", b_hr_scr_tot: "HR Screened (Total)",
                b_hr_rem_cbe: "HR Remarkable (CBE)", b_hr_rem_mam: "HR Remarkable (Mammo)", b_hr_rem_tot: "HR Remarkable (Total)",
                b_hr_link_cbe: "HR Linked (CBE)", b_hr_link_mam: "HR Linked (Mammo)", b_hr_link_tot: "HR Linked (Total)",
                b_as_scr_cbe: "Asymp Screened (CBE)", b_as_scr_mam: "Asymp Screened (Mammo)", b_as_scr_tot: "Asymp Screened (Total)",
                b_as_rem_cbe: "Asymp Remarkable (CBE)", b_as_rem_mam: "Asymp Remarkable (Mammo)", b_as_rem_tot: "Asymp Remarkable (Total)",
                b_as_link_cbe: "Asymp Linked (CBE)", b_as_link_mam: "Asymp Linked (Mammo)", b_as_link_tot: "Asymp Linked (Total)"
            }
            display_df = agg_df.rename(columns=clean_names)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(display_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_Breast_Cancer_Data.csv", mime="text/csv")
    else:
        st.info("No Breast Cancer data uploaded yet.")

def render_wash_tab(tab_title, df_key, selected_quarters, year, filter_rhus):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        
        valid_year_cols = ['Area', 'Month', 'Year']  
        for col in year_df.columns:
            if col not in valid_year_cols:
                if col in TARGET_WASH_COLS:
                    valid_year_cols.append(col)
                elif 'elig' in col.lower() or 'pop' in col.lower() or 'hh' in col.lower():
                    valid_year_cols.append(col)
                elif pd.api.types.is_numeric_dtype(year_df[col]):
                    if year_df[col].sum() > 0:
                        valid_year_cols.append(col)
                        
        filtered_df = year_df[year_df['Month'].isin(selected_quarters)]
        
        cols_to_keep_final = [c for c in filtered_df.columns if c in valid_year_cols]
        filtered_df = filtered_df[cols_to_keep_final]
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        safe_filename = tab_title.replace(" ", "_")
        
        cols_to_plot = [c for c in filtered_df.columns if c not in ['Area', 'Month', 'Year']]
        
        if cols_to_plot:
            agg_df = filtered_df.groupby('Area')[cols_to_plot].sum().reset_index()
            
            with st.expander(f"⚙️ Custom {tab_title} Indicators"):
                default_cols = [c for c in cols_to_plot if c != "Projected No. of HHs"]
                selected_cols = st.multiselect(f"Select specific {tab_title} indicators to visualize:", options=cols_to_plot, default=default_cols, key=f"ms_wash_{safe_filename}_{year}")
            
            if selected_cols:
                view_mode = st.radio("📊 Select Display Metric", ["Raw Counts", "Percentage (%) Coverage"], horizontal=True, key=f"toggle_view_wash_{safe_filename}_{year}")
                
                primary_metric = "HH with Access to Basic Safe Water Supply" if tab_title == "Safe Water" else "HH with Basic Sanitation Facility"
                has_primary = primary_metric in agg_df.columns and "Projected No. of HHs" in agg_df.columns
                
                if has_primary:
                    over_100_df = agg_df[agg_df[primary_metric] > agg_df["Projected No. of HHs"]]
                    if not over_100_df.empty:
                        flagged_rhus = over_100_df['Area'].tolist()
                        st.warning(f"🕵️‍♂️ **Data Quality Audit:** The following RHUs reported more covered households than their projected total, exceeding 100% coverage: **{', '.join(flagged_rhus)}**. Please verify their submissions.")

                st.markdown(f"#### 🏆 Highlights ({location_header.replace('📍 ', '')})")
                
                cols_per_row = 4
                rows = [st.columns(cols_per_row) for _ in range((len(selected_cols) + cols_per_row - 1) // cols_per_row)]
                
                provincial_hh = agg_df["Projected No. of HHs"].sum() if "Projected No. of HHs" in agg_df.columns else 0
                
                for i, col in enumerate(selected_cols):
                    row_idx = i // cols_per_row
                    col_idx = i % cols_per_row
                    total_val = agg_df[col].sum()
                    
                    if view_mode == "Percentage (%) Coverage" and "Projected No. of HHs" in agg_df.columns and col != "Projected No. of HHs":
                        perc = (total_val / provincial_hh) * 100 if provincial_hh > 0 else 0
                        rows[row_idx][col_idx].metric(label=f"{col} (Cov)", value=f"{perc:.1f}%")
                    else:
                        rows[row_idx][col_idx].metric(label=col, value=f"{int(total_val):,}")
                
                st.markdown("---")
                
                if has_primary:
                    st.markdown(f"#### 🌟 Performance Leaderboards ({tab_title})")
                    leader_df = agg_df[['Area', primary_metric, 'Projected No. of HHs']].copy()
                    leader_df['Coverage'] = np.where(leader_df['Projected No. of HHs'] > 0, (leader_df[primary_metric] / leader_df['Projected No. of HHs']) * 100, 0)
                    leader_df['Coverage'] = leader_df['Coverage'].clip(upper=100) 
                    leader_sorted = leader_df.sort_values(by='Coverage', ascending=False)
                    
                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        st.markdown("**Top Performing RHUs**")
                        top3 = leader_sorted.head(3)
                        fig_top3 = px.bar(top3, x='Area', y='Coverage', text_auto='.1f', color='Coverage', color_continuous_scale="Greens")
                        fig_top3.update_layout(xaxis_title="", yaxis_title="Coverage (%)", margin=dict(t=10, b=0), height=300)
                        st.plotly_chart(fig_top3, use_container_width=True, key=f"wash_top3_{safe_filename}_{year}")
                    
                    with col_l2:
                        st.markdown("**Action Required: Bottom RHUs**")
                        bot3 = leader_sorted.tail(3).sort_values(by='Coverage', ascending=True)
                        fig_bot3 = px.bar(bot3, x='Area', y='Coverage', text_auto='.1f', color='Coverage', color_continuous_scale="Reds_r")
                        fig_bot3.update_layout(xaxis_title="", yaxis_title="Coverage (%)", margin=dict(t=10, b=0), height=300)
                        st.plotly_chart(fig_bot3, use_container_width=True, key=f"wash_bot3_{safe_filename}_{year}")
                        
                    st.markdown("---")

                st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                
                chart_df = agg_df[['Area'] + selected_cols].copy()
                y_axis_label = "Count / Households"
                
                if view_mode == "Percentage (%) Coverage" and "Projected No. of HHs" in agg_df.columns:
                    for col in selected_cols:
                        if col != "Projected No. of HHs":
                            chart_df[col] = np.where(agg_df["Projected No. of HHs"] > 0, (chart_df[col] / agg_df["Projected No. of HHs"]) * 100, 0)
                            chart_df[col] = chart_df[col].round(1)
                    y_axis_label = "Coverage (%)"
                
                if len(selected_cols) == 1:
                    sort_order = st.radio("Sort RHUs by:", ["Alphabetical", "Highest to Lowest"], horizontal=True, key=f"sort_rhu_wash_{safe_filename}_{year}")
                    if sort_order == "Highest to Lowest":
                        chart_df = chart_df.sort_values(by=selected_cols[0], ascending=False)
                    else:
                        chart_df = chart_df.sort_values(by='Area', ascending=True)
                else:
                    chart_df = chart_df.sort_values(by='Area', ascending=True)

                melted = chart_df.melt(id_vars='Area', value_vars=selected_cols, var_name='Indicator', value_name='Count')
                
                fig_rhu = px.bar(melted, x='Area', y='Count', color='Indicator', barmode='group', title=f"{tab_title} Performance ({', '.join(selected_quarters)})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Safe, category_orders={"Area": chart_df['Area'].tolist()})
                
                if view_mode == "Percentage (%) Coverage":
                    fig_rhu.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="100% Target")
                    
                fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title=y_axis_label, margin=dict(t=60))
                st.plotly_chart(fig_rhu, use_container_width=True, key=f"rhu_wash_{safe_filename}_{year}")
                
                if has_primary:
                    st.markdown("---")
                    col_m1, col_m2 = st.columns(2)
                    
                    with col_m1:
                        st.markdown(f"#### 🗺️ Coverage Heatmap")
                        map_df = agg_df.copy()
                        map_df['Coverage (%)'] = np.where(map_df['Projected No. of HHs'] > 0, (map_df[primary_metric] / map_df['Projected No. of HHs']) * 100, 0).clip(0, 100)
                        map_df['Lat'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[0])
                        map_df['Lon'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[1])
                        map_df = map_df[map_df['Lat'] != 0] 
                        
                        fig_map = px.scatter_mapbox(map_df, lat="Lat", lon="Lon", hover_name="Area", 
                                                    hover_data={"Lat": False, "Lon": False, "Coverage (%)": ':.1f'}, 
                                                    color="Coverage (%)", size="Projected No. of HHs", 
                                                    color_continuous_scale="RdYlGn", size_max=20, zoom=8.5, 
                                                    center={"lat": 17.55, "lon": 120.75}, mapbox_style="carto-positron")
                        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                        st.plotly_chart(fig_map, use_container_width=True, key=f"wash_map_{safe_filename}_{year}")
                        
                    with col_m2:
                        st.markdown(f"#### ⚠️ Gap Analysis: Unserved Households")
                        gap_df = agg_df[['Area', primary_metric, 'Projected No. of HHs']].copy()
                        gap_df['Unserved'] = gap_df['Projected No. of HHs'] - gap_df[primary_metric]
                        gap_df['Unserved'] = gap_df['Unserved'].apply(lambda x: max(0, int(x))) 
                        gap_sorted = gap_df.sort_values('Unserved', ascending=True).tail(10) 
                        
                        fig_gap = px.bar(gap_sorted, x='Unserved', y='Area', orientation='h', text_auto=True, 
                                         title=f"RHUs with Highest Absolute Unserved HHs",
                                         color='Unserved', color_continuous_scale="Reds")
                        fig_gap.update_layout(xaxis_title="Number of Households Without Access", yaxis_title="RHU", margin=dict(t=40, b=0, l=0, r=0))
                        st.plotly_chart(fig_gap, use_container_width=True, key=f"wash_gap_{safe_filename}_{year}")

                if has_primary and len(year_df['Month'].unique()) > 1:
                    st.markdown("---")
                    st.markdown(f"#### 📈 Quarter-over-Quarter (QoQ) Trend")
                    trend_df = year_df.groupby('Month')[['Projected No. of HHs', primary_metric]].sum().reset_index()
                    
                    q_order = ["Q1", "Q2", "Q3", "Q4"]
                    trend_df['Month'] = pd.Categorical(trend_df['Month'], categories=q_order, ordered=True)
                    trend_df = trend_df.sort_values('Month').dropna()
                    
                    if view_mode == "Percentage (%) Coverage":
                        trend_df['Value'] = np.where(trend_df['Projected No. of HHs'] > 0, (trend_df[primary_metric] / trend_df['Projected No. of HHs']) * 100, 0)
                        trend_df['Value'] = trend_df['Value'].round(1)
                        y_label = "Coverage (%)"
                    else:
                        trend_df['Value'] = trend_df[primary_metric]
                        y_label = "Households with Access"
                        
                    fig_trend = px.line(trend_df, x='Month', y='Value', markers=True, 
                                        title=f"Trend: {primary_metric} ({year})", 
                                        color_discrete_sequence=["#1f77b4"])
                    
                    if view_mode == "Percentage (%) Coverage":
                        fig_trend.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="100% Target")
                        
                    fig_trend.update_layout(xaxis_title="Quarter", yaxis_title=y_label, margin=dict(t=40))
                    st.plotly_chart(fig_trend, use_container_width=True, key=f"wash_trend_{safe_filename}_{year}")

            else:
                st.info("👆 Please select at least one indicator to view the chart.")
                
        with st.expander(f"📄 View & Download Raw {tab_title} Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_Data.csv", mime="text/csv")
    else:
        st.info(f"No {tab_title} data uploaded yet. Please use the Data Uploader.")

def render_maternal_tab(tab_title, df_key, start_m, end_m, year, age_filter, filter_rhus):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        
        year_df = raw_df[raw_df['Year'] == year]
        
        months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        start_idx = months_order.index(start_m)
        end_idx = months_order.index(end_m)
        valid_months = months_order[start_idx:end_idx+1]
        
        filtered_df = year_df[year_df['Month'].isin(valid_months)]
        safe_filename = tab_title.replace(" ", "_")
        
        # --- CROSS-FILE DATA MERGING (PULL DENOMINATORS FROM LIVEBIRTHS TEMPLATE FIRST) ---
        if 'Livebirths' in st.session_state['fhsis_data']:
            lb_df = st.session_state['fhsis_data']['Livebirths']
            lb_year = lb_df[lb_df['Year'] == year]
            lb_filt = lb_year[lb_year['Month'].isin(valid_months)]
            if not lb_filt.empty:
                lb_cols = [c for c in lb_filt.columns if c not in filtered_df.columns and c not in ['Year']]
                if lb_cols:
                    filtered_df = pd.merge(filtered_df, lb_filt[['Area', 'Month'] + lb_cols], on=['Area', 'Month'], how='left').fillna(0)
        # --------------------------------------------------------------------------------
        
        if filter_rhus and "Abra (Total)" not in filter_rhus:
            filtered_df = filtered_df[filtered_df['Area'].isin(filter_rhus)]
        
        elig_cols = [c for c in filtered_df.columns if 'elig' in c.lower() or 'pop' in c.lower()]
        
        cols_to_plot = []
        for col in filtered_df.columns:
            if col in ['Area', 'Month', 'Year'] or col in elig_cols:
                continue
                
            filter_suffix = str(age_filter).lower()
            
            is_match = False
            if filter_suffix == "total":
                if col.lower().endswith("_total") or ("total" in col.lower() and not any(age in col for age in ["10-14", "15-19", "20-49"])):
                    is_match = True
            else:
                if col.lower().endswith(filter_suffix) or f"_{filter_suffix}" in col.lower():
                    is_match = True
                elif filter_suffix in col.lower() and "adolescent" in col.lower():
                    if "total" in col.lower():
                        is_match = True
                        
            if is_match:
                mapped_name = get_clean_indicator_name(col)
                if mapped_name and mapped_name.split('.')[0].isdigit():
                    
                    if "Total Deliveries" in mapped_name and tab_title not in ["Antenatal Care (ANC)", "Postpartum Care (PPC)"]:
                        continue
                        
                    if col not in cols_to_plot:
                        cols_to_plot.append(col)
        
        if cols_to_plot:
            all_numeric_cols = [c for c in filtered_df.columns if pd.api.types.is_numeric_dtype(filtered_df[c]) and c not in ['Area', 'Month', 'Year']]
            agg_dict = {col: 'sum' for col in all_numeric_cols}
            for ec in elig_cols: agg_dict[ec] = 'max' 
            
            agg_df = filtered_df.groupby('Area').agg(agg_dict).reset_index()
            
            default_cols = cols_to_plot
            
            with st.expander(f"⚙️ Custom {tab_title} Indicators"):
                selected_cols = st.multiselect(
                    f"Select specific {tab_title} indicators to visualize:", 
                    options=cols_to_plot, 
                    default=default_cols, 
                    key=f"ms_mat_{safe_filename}_{year}_{age_filter}",
                    format_func=get_clean_indicator_name
                )
            
            if selected_cols:
                view_mode = st.radio("📊 Select Display Metric", ["Raw Counts", "Percentage (%) Coverage"], horizontal=True, key=f"toggle_view_mat_{safe_filename}_{year}_{age_filter}")
                
                if view_mode == "Percentage (%) Coverage":
                    if "ANC" in tab_title:
                        allowed_perc_indicators = [
                            "2. Delivered with at least 4 ANC visits",
                            "9. Delivered & completed at least 8ANC (a+b)"
                        ]
                        selected_cols = [c for c in selected_cols if get_clean_indicator_name(c) in allowed_perc_indicators]
                        if not selected_cols:
                            st.info("💡 In Percentage view, the ANC dashboard strictly tracks **ANC 4** and **ANC 8**. Please select them from the dropdown above.")
                    
                    elif "PPC" in tab_title:
                        allowed_perc_indicators = [
                            "2. Completed at least 2 PP check-ups",
                            "9. Women gave birth completed at least 4PNC =(a+b)",
                            "10. PP women who completed iron with folic acid",
                            "11. PP women given Vitamin A supplementation"
                        ]
                        selected_cols = [c for c in selected_cols if get_clean_indicator_name(c) in allowed_perc_indicators]
                        if not selected_cols:
                            st.info("💡 In Percentage view, the PPC dashboard strictly tracks **PP 2**, **PNC 4**, **Iron w/ Folic Acid**, and **Vitamin A**. Please select them from the dropdown above.")
                    
                    selected_cols = [c for c in selected_cols if get_clean_indicator_name(c) != "0. Total Deliveries"]

                if selected_cols:
                    st.markdown(f"#### 🏆 Highlights ({location_header.replace('📍 ', '')}) | {age_filter}")
                    cols_per_row = 4
                    rows = [st.columns(cols_per_row) for _ in range((len(selected_cols) + cols_per_row - 1) // cols_per_row)]
                    
                    for i, col in enumerate(selected_cols):
                        row_idx = i // cols_per_row
                        col_idx = i % cols_per_row
                        total_val = agg_df[col].sum()
                        clean_name = get_clean_indicator_name(col)
                        
                        if view_mode == "Percentage (%) Coverage":
                            denom_col = get_maternal_denominator(col, age_filter, agg_df.columns)
                            if denom_col and denom_col in agg_df.columns:
                                denom_val = agg_df[denom_col].sum()
                                perc = (total_val / denom_val) * 100 if denom_val > 0 else 0
                                rows[row_idx][col_idx].metric(label=f"{clean_name} (%)", value=f"{perc:.1f}%")
                            else:
                                rows[row_idx][col_idx].metric(label=f"{clean_name} (Count)", value=f"{int(total_val):,}")
                        else:
                            rows[row_idx][col_idx].metric(label=clean_name, value=f"{int(total_val):,}")
                    
                    st.markdown("---")
                    chart_title = f"Summary ({start_m} - {end_m}) | Group: {age_filter}"
                    
                    cascade_data = pd.DataFrame({
                        'Indicator': [get_clean_indicator_name(c) for c in selected_cols],
                        'Count': [agg_df[c].sum() for c in selected_cols]
                    })
                    
                    cascade_data['Sort_Key'] = cascade_data['Indicator'].apply(lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 99)
                    cascade_data = cascade_data.sort_values(by='Sort_Key', ascending=True)

                    # --- CASCADE SMART HIDE LOGIC ---
                    # Calculate if the user broke the pipeline sequence
                    removed_count = len(cols_to_plot) - len(selected_cols)

                    if ("ANC" in tab_title or "PPC" in tab_title) and removed_count <= 1:
                        st.markdown(f"#### 🌪️ {tab_title} Cascade")
                        st.markdown("Tracking the retention and drop-off rate of women throughout their maternal care journey.")
                        
                        fig_main = px.funnel(cascade_data, x='Count', y='Indicator', title=chart_title, color_discrete_sequence=["#9B59B6"])
                        fig_main.update_traces(textposition="inside")
                    else:
                        st.markdown(f"#### 📊 {tab_title} Interventions & Screenings")
                        
                        # Show a helpful note if we actively hid the funnel
                        if ("ANC" in tab_title or "PPC" in tab_title) and removed_count > 1:
                            st.info("💡 **Cascade View Hidden:** Multiple pipeline steps were removed (or Percentage view is active). Falling back to a standard comparison chart.")
                        else:
                            st.markdown("Comparing the total volume of specific interventions or screening yields.")
                        
                        fig_main = px.bar(cascade_data, x='Indicator', y='Count', title=chart_title, text_auto=True, color='Indicator', color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig_main.update_traces(textposition="outside", cliponaxis=False)
                        fig_main.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total Women", margin=dict(t=40))

                    st.plotly_chart(fig_main, use_container_width=True, key=f"mat_main_chart_{safe_filename}_{year}_{age_filter}")
                    
                    st.markdown("---")
                    st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                    
                    chart_df = agg_df[['Area']].copy()
                    valid_chart_cols = []
                    
                    if view_mode == "Percentage (%) Coverage":
                        y_axis_label = "Coverage (%)"
                        for col in selected_cols:
                            denom_col = get_maternal_denominator(col, age_filter, agg_df.columns)
                            if denom_col and denom_col in agg_df.columns:
                                chart_df[col] = np.where(agg_df[denom_col] > 0, (agg_df[col] / agg_df[denom_col]) * 100, 0)
                                chart_df[col] = chart_df[col].round(1)
                                valid_chart_cols.append(col)
                                
                        if len(valid_chart_cols) < len(selected_cols):
                            st.info("💡 Note: Only indicators with an official DOH percentage calculation are plotted on the chart to maintain accurate scaling.")
                    else:
                        y_axis_label = "Number of Women"
                        for col in selected_cols:
                            chart_df[col] = agg_df[col]
                            valid_chart_cols.append(col)
                    
                    if valid_chart_cols:
                        if len(valid_chart_cols) == 1:
                            sort_order = st.radio("Sort RHUs by:", ["Alphabetical", "Highest to Lowest"], horizontal=True, key=f"sort_rhu_mat_{safe_filename}_{year}_{age_filter}")
                            if sort_order == "Highest to Lowest":
                                chart_df = chart_df.sort_values(by=valid_chart_cols[0], ascending=False)
                            else:
                                chart_df = chart_df.sort_values(by='Area', ascending=True)
                        else:
                            chart_df = chart_df.sort_values(by='Area', ascending=True)

                        melted = chart_df.melt(id_vars='Area', value_vars=valid_chart_cols, var_name='Indicator', value_name='Count')
                        melted['Indicator'] = melted['Indicator'].apply(get_clean_indicator_name)
                        
                        fig_rhu = px.bar(melted, x='Area', y='Count', color='Indicator', barmode='group', title=f"All RHUs ({start_m} - {end_m})", text_auto=True, color_discrete_sequence=px.colors.qualitative.Prism, category_orders={"Area": chart_df['Area'].tolist()})
                        if view_mode == "Percentage (%) Coverage":
                            fig_rhu.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% Target")
                        fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                        fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title=y_axis_label, margin=dict(t=60))
                        st.plotly_chart(fig_rhu, use_container_width=True, key=f"rhu_mat_{safe_filename}_{year}_{age_filter}")
                    
                    st.markdown("---")
                    st.markdown(f"#### 📈 Monthly Trend Analysis")
                    trend_agg = filtered_df.groupby('Month').sum(numeric_only=True).reset_index()
                    
                    trend_agg['Month'] = pd.Categorical(trend_agg['Month'], categories=months_order, ordered=True)
                    trend_agg = trend_agg.sort_values('Month').dropna()
                    
                    trend_chart_df = pd.DataFrame({'Month': trend_agg['Month']})
                    valid_trend_cols = []
                    
                    if view_mode == "Percentage (%) Coverage":
                        for col in selected_cols:
                            denom_col = get_maternal_denominator(col, age_filter, trend_agg.columns)
                            if denom_col and denom_col in trend_agg.columns:
                                trend_chart_df[col] = [
                                    (v / denom_val * 100) if denom_val > 0 else 0 
                                    for v, denom_val in zip(trend_agg[col], trend_agg[denom_col])
                                ]
                                trend_chart_df[col] = trend_chart_df[col].round(1)
                                valid_trend_cols.append(col)
                    else:
                        for col in selected_cols:
                            trend_chart_df[col] = trend_agg[col]
                            valid_trend_cols.append(col)
                        
                    if valid_trend_cols:
                        trend_melted = trend_chart_df.melt(id_vars='Month', value_vars=valid_trend_cols, var_name='Indicator', value_name='Count')
                        trend_melted['Indicator'] = trend_melted['Indicator'].apply(get_clean_indicator_name)
                        
                        fig_trend = px.line(trend_melted, x='Month', y='Count', color='Indicator', markers=True, title=f"Trend ({year})", color_discrete_sequence=px.colors.qualitative.Prism)
                        fig_trend.update_layout(xaxis_title="Month", yaxis_title=y_axis_label, margin=dict(t=40))
                        st.plotly_chart(fig_trend, use_container_width=True, key=f"mat_trend_{safe_filename}_{year}_{age_filter}")
                
            else:
                st.info("👆 Please select at least one indicator from the dropdown above to view the charts.")
                
        with st.expander(f"📄 View & Download Raw {tab_title} Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_{age_filter}_Data.csv", mime="text/csv")
    else:
        st.info(f"No {tab_title} data uploaded yet. Please use the Data Uploader.")


# --- PAGES ---
if page == "🏠 Home":
    
    # Helper function to convert images so HTML can read them securely
    def get_base64(img_path):
        if os.path.exists(img_path):
            with open(img_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        return ""

    # CHANGE THESE FILENAMES IF YOURS ARE DIFFERENT!
    abra_b64 = get_base64("Abra_provincial_seal.png")
    pho_b64 = get_base64("PHO logo.png")
    doh_b64 = get_base64("DOH logo.png")

    # --- HTML FLEXBOX ROW & TOP PADDING FIX ---
    st.markdown(f"""
        <style>
        /* Pushes the entire app up higher on the screen */
        .block-container {{
            padding-top: 2.5rem !important; 
        }}
        
        /* Perfectly centers the logos and aligns their middles */
        .logo-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 40px; 
            margin-bottom: 10px;
        }}
        </style>
        
        <div class="logo-container">
            <img src="data:image/png;base64,{abra_b64}" style="height: 130px;">
            <img src="data:image/png;base64,{pho_b64}" style="height: 145px;"> 
            <img src="data:image/png;base64,{doh_b64}" style="height: 130px;">
        </div>
        
        <div style="text-align: center; padding: 0.5rem 0;">
            <h1>Provincial Health Office (PHO)</h1>
            <h2>FHSIS Health & Analytics Portal</h2>
            <p style="font-size: 1.2rem; color: gray;">Engineered for accuracy. Built for action.</p>
        </div>
        <hr>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🏛️ Welcome to the Provincial Command Center")
    st.markdown("""
    This application is an enterprise-grade reporting engine designed to automatically ingest, clean, and visualize Field Health Services Information System (FHSIS) data across all **27 Rural Health Units (RHUs)** in the province of Abra. 

    **Active Health Modules:**
    * 👶 **Child Immunization:** Tracking routine antigens, Fully Immunized Child (FIC) targets, and dropout rates.
    * 🩺 **Non-Communicable Diseases (NCD):** Monitoring adult/senior lifestyle risks, diagnostic yields, and Cervical/Breast Cancer screenings.
    * 🚰 **Environmental Health (WASH):** Mapping household access to basic safe water and sanitation facilities.
    * 🤰 **Maternal Health:** Analyzing the complete cascade of care across Antenatal, Postpartum, and Nutritional interventions.
    * 💀 **Mortality & Injuries:** Tracking premature NCD deaths and traffic-related fatalities.
    * 👨‍👩‍👧 **Family Planning:** *(Module actively under construction!)*

    **Core Engine Capabilities:**
    * **Automated Data ETL:** Safely parses messy, merged, and multi-sheet DOH Excel templates directly into a secure cloud database.
    * **Geospatial & Trend Analysis:** Transforms raw numbers into interactive heatmaps, Year-over-Year (YoY) comparisons, and automated FHSIS scorecards.

    *Use the sidebar navigation to explore the provincial dashboards. Authorized PHO Admins can log in at the bottom of the sidebar to securely upload new DOH data.*
    """)
    st.info("💡 **Tip:** Navigate to the **Immunization Dashboard** to view the Executive Summary and generate your monthly PHO report.")

elif page == "👶 Immunization Dashboard":
    st.title("💉 Child Immunization Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year} &nbsp; | &nbsp; **👥 Demographic:** {gender_filter}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Time Filter")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("Time Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed")
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"), label_visibility="collapsed")
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"), label_visibility="collapsed")
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab_exec, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⭐ Executive Summary",
        "👶 Birth Doses (BCG/HepB)", 
        "🛡️ Penta (DPT-HiB-HepB)", 
        "💧 Polio (OPV/IPV)", 
        "🫁 Pneumococcal (PCV)", 
        "🎯 MMR, FIC & CIC"
    ])
    
    with tab_exec:
        st.markdown(f"### 🏆 Executive Overview ({location_header.replace('📍 ', '')})")
        st.markdown("High-level snapshot of critical DOH performance metrics and forecasting.")
        
        if "MMR" in st.session_state['fhsis_data'] and "Penta" in st.session_state['fhsis_data']:
            mmr_df = filter_data(st.session_state['fhsis_data']["MMR"], start_month, end_month, gender_filter, selected_year)
            penta_df = filter_data(st.session_state['fhsis_data']["Penta"], start_month, end_month, gender_filter, selected_year)
            
            if rhu_filter and "Abra (Total)" not in rhu_filter:
                mmr_df = mmr_df[mmr_df['Area'].isin(rhu_filter)]
                penta_df = penta_df[penta_df['Area'].isin(rhu_filter)]
            
            fic_col = next((c for c in mmr_df.columns if "FIC" in c and "%" not in c and "DEFICIT" not in c.upper() and "PREVIOUS" not in c.upper()), None)
            cic_col = next((c for c in mmr_df.columns if "CIC" in c and "%" not in c and "DEFICIT" not in c.upper() and "PREVIOUS" not in c.upper()), None)
            elig_col = next((c for c in mmr_df.columns if 'elig' in c.lower() or 'pop' in c.lower()), None)
            
            p1_col = next((c for c in penta_df.columns if (" 1" in c or "1_" in c) and "%" not in c and "DEFICIT" not in c.upper()), None)
            p3_col = next((c for c in penta_df.columns if (" 3" in c or "3_" in c) and "%" not in c and "DEFICIT" not in c.upper()), None)
            
            if fic_col and elig_col:
                prov_fic = mmr_df[fic_col].sum()
                prov_cic = mmr_df[cic_col].sum() if cic_col else 0
                p1_tot = penta_df[p1_col].sum() if p1_col else 0
                p3_tot = penta_df[p3_col].sum() if p3_col else 0
                
                rhu_fic = mmr_df.groupby('Area').agg({fic_col: 'sum', elig_col: 'max'}).reset_index()
                prov_elig = mmr_df.groupby('Area')[elig_col].max().sum() 
                
                curr_cov = (prov_fic / prov_elig * 100) if prov_elig > 0 else 0
                cic_cov = (prov_cic / prov_elig * 100) if prov_elig > 0 else 0
                
                months_idx_start = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(start_month)
                months_idx_end = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(end_month)
                months_count = months_idx_end - months_idx_start + 1
                
                projected_fic = (prov_fic / months_count) * 12 if months_count > 0 else 0
                projected_cov = min((projected_fic / prov_elig * 100), 100) if prov_elig > 0 else 0
                
                prov_drop = 0
                if p1_col and p3_col:
                    prov_drop = ((p1_tot - p3_tot) / p1_tot * 100) if p1_tot > 0 else 0
                
                dq_warnings = []
                fic_label = "Fully Immunized Child (FIC)"
                cic_label = "Completely Immunized (CIC)"
                drop_label = "Dropout (Penta 1-3)"
                
                if curr_cov > 110:
                    fic_label += " ⚠️"
                    dq_warnings.append(f"**FIC Coverage ({curr_cov:.1f}%) exceeds 110%:** Usually indicates an outdated eligible population denominator or out-of-catchment patients being counted.")
                
                if prov_fic == prov_cic and prov_fic > 0:
                    cic_label += " ⚠️"
                    dq_warnings.append(f"**FIC and CIC counts match exactly ({prov_fic:,.0f}):** Highly improbable. Check if an RHU accidentally duplicated the FIC column into the CIC column on the Excel sheet.")
                elif cic_cov > 110:
                    cic_label += " ⚠️"
                    dq_warnings.append(f"**CIC Coverage ({cic_cov:.1f}%) exceeds 110%.**")
                    
                if prov_drop < 0:
                    drop_label += " ⚠️"
                    dq_warnings.append(f"**Negative Penta Dropout ({prov_drop:.1f}%):** More Penta 3 doses given than Penta 1. Verify if this is an expected catch-up surge or a data entry error.")

                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                col_e1.metric(fic_label, f"{prov_fic:,.0f}", f"Current Cov: {curr_cov:.1f}%")
                
                proj_delta = projected_cov - curr_cov
                col_e2.metric("End-of-Year FIC Forecast", f"{projected_cov:.1f}%", f"{proj_delta:+.1f}% vs Current", delta_color="normal" if projected_cov >= 95 else "off")
                
                if cic_col:
                    col_e3.metric(cic_label, f"{prov_cic:,.0f}", f"Current Cov: {cic_cov:.1f}%")
                else:
                    col_e3.metric("Completely Immunized (CIC)", "N/A")
                    
                col_e4.metric(drop_label, f"{prov_drop:.1f}%", "Target: < 10%", delta_color="inverse")
                
                if dq_warnings:
                    st.warning("🕵️‍♂️ **Automated Data Quality Audit:** Potential anomalies detected in the aggregated data.")
                    for w in dq_warnings:
                        st.markdown(f"- {w}")

                with st.expander("🖨️ Generate Printable PHO Report", expanded=False):
                    # --- ADDED: THE HIDDEN PRINT HEADER ---
                    st.markdown("""
                    <div class='print-only-header'>
                        <h3>Republic of the Philippines</h3>
                        <h3>Department of Health</h3>
                        <h2>Abra Provincial Health Office</h2>
                        <hr>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"### Immunization Report")
                    st.markdown(f"**Location Filter:** {location_header.replace('📍 ', '')}")
                    st.markdown(f"**Reporting Period:** {start_month} to {end_month} {selected_year} | **Demographic:** {gender_filter}")
                    st.markdown("---")
                    st.markdown(f"""
                    **1. Performance Summary**
                    * **Total Fully Immunized Children (FIC):** {prov_fic:,.0f} 
                    * **Current FIC Coverage Rate:** {curr_cov:.1f}% (DOH Target: 95%)
                    * **Year-End FIC Forecast:** {projected_cov:.1f}%
                    * **Penta 1 to Penta 3 Dropout Rate:** {prov_drop:.1f}% (Target: Below 10%)
                    """)
                    
                    rhu_fic['Coverage'] = (rhu_fic[fic_col] / rhu_fic[elig_col] * 100).fillna(0)
                    rhu_sorted = rhu_fic.sort_values(by='Coverage', ascending=False)
                    top_list = rhu_sorted.head(3)
                    bot_list = rhu_sorted.tail(3).sort_values(by='Coverage', ascending=True)
                    
                    st.markdown("**2. Top Performing Municipalities (FIC Coverage)**")
                    for index, row in top_list.iterrows():
                        st.markdown(f"* **{row['Area']}:** {row['Coverage']:.1f}%")
                        
                    st.markdown("**3. Action Required: Bottom Municipalities (FIC Coverage)**")
                    for index, row in bot_list.iterrows():
                        st.markdown(f"* **{row['Area']}:** {row['Coverage']:.1f}%")
                    
                    if dq_warnings:
                        st.markdown("**4. Data Quality Flags (Requires RHU Verification)**")
                        for w in dq_warnings:
                            st.markdown(f"* {w}")
                    
                    st.info("Tip: Press **Ctrl + P** (Windows) or **Cmd + P** (Mac) to save this cleanly to PDF or print for your PHO meeting.")

                st.markdown("---")
                col_lead1, col_lead2 = st.columns(2)
                
                with col_lead1:
                    st.markdown("#### 🌟 Top RHUs (FIC)")
                    top3 = rhu_sorted.head(3)
                    fig_top3 = px.bar(top3, x='Area', y='Coverage', text_auto='.1f', color='Coverage', color_continuous_scale="Greens")
                    fig_top3.update_layout(xaxis_title="", yaxis_title="Coverage (%)", margin=dict(t=30, b=0))
                    st.plotly_chart(fig_top3, use_container_width=True, key=f"top3_exec_fic_{selected_year}")
                    
                with col_lead2:
                    st.markdown("#### ⚠️ Bottom RHUs (FIC)")
                    bot3 = rhu_sorted.tail(3).sort_values(by='Coverage', ascending=True)
                    fig_bot3 = px.bar(bot3, x='Area', y='Coverage', text_auto='.1f', color='Coverage', color_continuous_scale="Reds_r")
                    fig_bot3.update_layout(xaxis_title="", yaxis_title="Coverage (%)", margin=dict(t=30, b=0))
                    st.plotly_chart(fig_bot3, use_container_width=True, key=f"bot3_exec_fic_{selected_year}")

                st.markdown("---")
                st.markdown("#### 🚀 Target Forecasting (FIC Coverage)")
                forecast_df = pd.DataFrame({
                    "Metric": ["Current Coverage", "Projected Year-End", "DOH Target"],
                    "Coverage (%)": [curr_cov, projected_cov, 95]
                })
                fig_forecast = px.bar(forecast_df, x="Coverage (%)", y="Metric", orientation='h', 
                                      color="Metric", text_auto=".1f",
                                      color_discrete_map={"Current Coverage": "#1f77b4", "Projected Year-End": "#ff7f0e", "DOH Target": "red"})
                fig_forecast.add_vline(x=95, line_dash="dash", line_color="red", annotation_text="95% Target")
                fig_forecast.update_layout(showlegend=False, xaxis_range=[0, max(100, projected_cov + 5)])
                st.plotly_chart(fig_forecast, use_container_width=True, key=f"forecast_exec_{selected_year}")

        else:
            st.info("Upload both 'Pentavalent' and 'MMR/FIC' data via the Data Uploader to unlock the Executive Summary.")

    with tab1: render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG", "Hep"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with tab2: render_tab_content("Pentavalent", "Penta", ["DPT-HiB-HepB 1", "DPT-HiB-HepB 2", "DPT-HiB-HepB 3", "Penta 1", "Penta 2", "Penta 3"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with tab3: render_tab_content("Polio", "Polio", ["OPV 1", "OPV 2", "OPV 3", "IPV 1", "IPV 2"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with tab4: render_tab_content("Pneumococcal", "PCV", ["PCV 1", "PCV 2", "PCV 3"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with tab5: render_tab_content("MMR/MCV, FIC and CIC", "MMR", ["MMR", "MCV", "13-23", "FIC", "CIC"], start_month, end_month, gender_filter, selected_year, rhu_filter)

elif page == "🩺 NCD Dashboard":
    st.title("🩺 Non-Communicable Disease (NCD) Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year} &nbsp; | &nbsp; **👥 Demographic:** {gender_filter}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Time Filter")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("Time Aggregation", ["Monthly", "Quarterly"], horizontal=True, label_visibility="collapsed", key="ncd_time")
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"), label_visibility="collapsed", key="ncd_m")
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"), label_visibility="collapsed", key="ncd_q")
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    ncd_tab1, ncd_tab2, ncd_tab3, ncd_tab4 = st.tabs([
        "👤 Adults Risk (20-59)", 
        "👴 Seniors Risk (≥60)", 
        "🎗️ Cervical Cancer", 
        "🎀 Breast Cancer"
    ])
    
    with ncd_tab1: render_ncd_tab_content("Adults Risk Assessment", "Adults_Risk", ["risk assessed", "smoking", "smoker", "alcohol", "overweight", "obese", "physical activity", "unhealthy diet", "hypertensive", "type 2 dm"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with ncd_tab2: render_ncd_tab_content("Seniors Risk Assessment", "Seniors_Risk", ["risk assessed", "smoking", "smoker", "alcohol", "overweight", "obese", "physical activity", "unhealthy diet", "hypertensive", "type 2 dm"], start_month, end_month, gender_filter, selected_year, rhu_filter)
    with ncd_tab3: render_cervical_cancer_tab("Cervical_Cancer", start_month, end_month, gender_filter, selected_year, rhu_filter)
    with ncd_tab4: render_breast_cancer_tab("Breast_Cancer", start_month, end_month, gender_filter, selected_year, rhu_filter)

elif page == "🚰 WASH Dashboard":
    st.title("🚰 Water, Sanitation, and Hygiene (WASH) Dashboard")
    st.markdown(f"**{location_header}** &nbsp; | &nbsp; **📅 Year:** {selected_year}")
    st.markdown("---")
    
    st.markdown("##### ⏳ Quarterly Time Filter")
    quarters_list = ["Q1", "Q2", "Q3", "Q4"]
    selected_quarters = st.multiselect("Select Quarters to Aggregate", quarters_list, default=quarters_list)
    
    if not selected_quarters:
        st.warning("Please select at least one quarter to view data.")
    else:
        st.markdown("<br>", unsafe_allow_html=True)
        wash_tab1, wash_tab2 = st.tabs(["🚰 Safe Water", "🚽 Sanitation"])
        
        with wash_tab1: render_wash_tab("Safe Water", "Safe_Water", selected_quarters, selected_year, rhu_filter)
        with wash_tab2: render_wash_tab("Sanitation", "Sanitation", selected_quarters, selected_year, rhu_filter)

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
            "Calcium, MMS & Deworming": ("Calcium_MMS", ["calcium carbonate", "multiple micronutrient", "deworming tablet"]),
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
