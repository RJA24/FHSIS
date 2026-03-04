import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

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

def save_data_to_gsheets(data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    for app_key, df in data_dict.items():
        sheet_name = SHEET_MAPPING[app_key]
        with st.spinner(f"Saving {app_key} to cloud database..."):
            conn.update(worksheet=sheet_name, data=df)

def load_data_from_gsheets():
    loaded_data = {}
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        for app_key, sheet_name in SHEET_MAPPING.items():
            try:
                df = conn.read(worksheet=sheet_name, ttl=0) 
                if not df.empty and 'Area' in df.columns:
                    loaded_data[app_key] = df
            except Exception:
                pass 
    except Exception as e:
        st.error("Google Sheets connection not fully configured yet. Please check your secrets.toml file.")
    return loaded_data

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

# --- DATA CLEANING FUNCTION ---
@st.cache_data
def load_and_clean_fhsis_data(uploaded_file, year):
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
            df_clean['Year'] = year
            
            for col in df_clean.columns:
                if col not in ['Area', 'Month', 'Year', 'Interpretation', 'Recommendation/Actions Taken']:
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
        selected_year = st.selectbox("Select Year", options=[2025, 2026, 2027])
        gender_filter = st.selectbox("Select Demographic", options=["Total", "Male", "Female"])

# --- INITIALIZE SESSION STATE FROM GOOGLE SHEETS ---
if 'fhsis_data' not in st.session_state:
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
    for col in filtered_df.columns:
        if col.endswith(f"_{gender}") or col in ['Interpretation', 'Recommendation/Actions Taken'] or "%" in col or "elig" in col.lower() or "pop" in col.lower():
            cols_to_keep.append(col)
            
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    
    if len(cols_to_keep) > 2:
        return filtered_df[cols_to_keep]
    return filtered_df

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def render_tab_content(tab_title, df_key, base_metrics, start_m, end_m, gender, year):
    if df_key in st.session_state['fhsis_data']:
        raw_df = st.session_state['fhsis_data'][df_key]
        filtered_df = filter_data(raw_df, start_m, end_m, gender, year)
        
        safe_filename = tab_title.replace(" ", "_").replace("/", "_").replace("&", "and")
        elig_cols = [c for c in filtered_df.columns if 'elig' in c.lower() or 'pop' in c.lower()]
        
        cols_to_plot = []
        for base in base_metrics:
            for col in filtered_df.columns:
                if base.lower() in col.lower() and col.endswith(f"_{gender}"):
                    if col not in cols_to_plot:  
                        cols_to_plot.append(col)
        
        if cols_to_plot:
            agg_dict = {col: 'sum' for col in cols_to_plot}
            for ec in elig_cols:
                agg_dict[ec] = 'max' 
                
            agg_df = filtered_df.groupby('Area').agg(agg_dict).reset_index()
            
            selected_cols = st.multiselect(
                "🎯 Select Indicators to Display",
                options=cols_to_plot,
                default=cols_to_plot,
                key=f"ms_{safe_filename}"
            )
            
            view_mode = st.radio(
                "📊 Select Display Metric", 
                ["Raw Counts", "Percentage (%) Coverage"], 
                horizontal=True, 
                key=f"toggle_{safe_filename}"
            )

            if selected_cols:
                provincial_antigens = {col: agg_df[col].sum() for col in selected_cols}
                provincial_elig = sum([agg_df[ec].sum() for ec in elig_cols[:1]]) if elig_cols else 1
                
                st.markdown("#### 🏆 Province-Wide Summary")
                kpi_cols = st.columns(len(selected_cols))
                
                for i, col in enumerate(selected_cols):
                    total_val = provincial_antigens[col]
                    clean_name = col.replace(f"_{gender}", "")
                    
                    if view_mode == "Percentage (%) Coverage" and elig_cols:
                        perc = (total_val / provincial_elig) * 100 if provincial_elig > 0 else 0
                        with kpi_cols[i]:
                            st.metric(label=f"{clean_name} Target Achieved", value=f"{perc:.1f}%")
                    else:
                        with kpi_cols[i]:
                            st.metric(label=f"Total {clean_name}", value=f"{int(total_val):,}")
                
                st.markdown("---")
                
                chart_df = agg_df[['Area'] + selected_cols + elig_cols].copy()
                abra_total_df = pd.DataFrame()
                abra_total_df['Vaccine/Antigen'] = selected_cols
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    main_elig_col = elig_cols[0]
                    for col in selected_cols:
                        chart_df[col] = np.where(chart_df[main_elig_col] > 0, (chart_df[col] / chart_df[main_elig_col]) * 100, 0)
                        chart_df[col] = chart_df[col].round(1)
                    
                    prov_counts = [provincial_antigens[c] for c in selected_cols]
                    abra_total_df['Count'] = [(c / provincial_elig * 100) if provincial_elig > 0 else 0 for c in prov_counts]
                    abra_total_df['Count'] = abra_total_df['Count'].round(1)
                    y_axis_label = "Coverage (%)"
                else:
                    abra_total_df['Count'] = [provincial_antigens[c] for c in selected_cols]
                    y_axis_label = "Number of Children"

                st.markdown(f"#### 📈 {tab_title} - Abra Province Total")
                abra_total_df['Vaccine/Antigen'] = abra_total_df['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                
                fig_abra = px.bar(abra_total_df, x='Vaccine/Antigen', y='Count', color='Vaccine/Antigen',
                                  title=f"Abra Province Total ({start_m} - {end_m})",
                                  text_auto=True,
                                  color_discrete_sequence=px.colors.qualitative.Pastel)
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    fig_abra.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                    
                fig_abra.update_traces(textfont_size=14, textposition="outside", cliponaxis=False)
                fig_abra.update_layout(xaxis_title="Antigen", yaxis_title=y_axis_label, showlegend=False, margin=dict(t=60))
                st.plotly_chart(fig_abra, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_Provincial_Total_{safe_filename}', 'scale': 4}})

                st.markdown("---")
                
                st.markdown(f"#### 📊 {tab_title} - RHU Breakdown")
                
                melted = chart_df.melt(id_vars='Area', value_vars=selected_cols, var_name='Vaccine/Antigen', value_name='Count')
                melted['Vaccine/Antigen'] = melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                
                fig_rhu = px.bar(melted, x='Area', y='Count', color='Vaccine/Antigen', barmode='group',
                             title=f"All RHUs ({start_m} - {end_m})",
                             text_auto=True,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    fig_rhu.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                    
                fig_rhu.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
                fig_rhu.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title=y_axis_label, legend_title="Antigen", margin=dict(t=60))
                st.plotly_chart(fig_rhu, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_RHU_Breakdown_{safe_filename}', 'scale': 4}})
                
                st.markdown("---")
                
                st.markdown(f"#### 🏆 Top 5 Performing RHUs (Average)")
                
                top5_df = chart_df.copy()
                top5_df['Rank_Metric'] = top5_df[selected_cols].mean(axis=1)
                top5_df = top5_df.sort_values(by='Rank_Metric', ascending=True).tail(5)
                
                fig_top5 = px.bar(top5_df, x='Rank_Metric', y='Area', orientation='h',
                                  title=f"Top 5 RHUs ({start_m} - {end_m})",
                                  text_auto='.1f' if view_mode == "Percentage (%) Coverage" else True,
                                  color='Rank_Metric',
                                  color_continuous_scale="Greens")
                
                fig_top5.update_layout(xaxis_title=y_axis_label, yaxis_title="Rural Health Unit (RHU)", showlegend=False, margin=dict(t=60))
                st.plotly_chart(fig_top5, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_Top5_RHUs_{safe_filename}', 'scale': 4}})
                
                # --- NEW: GEOSPATIAL MAP ---
                st.markdown("---")
                st.markdown(f"#### 🗺️ Provincial Heatmap")
                
                map_df = chart_df.copy()
                map_df['Rank_Metric'] = map_df[selected_cols].mean(axis=1)
                map_df['Lat'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[0])
                map_df['Lon'] = map_df['Area'].map(lambda x: ABRA_COORDS.get(x, (0,0))[1])
                map_df = map_df[map_df['Lat'] != 0] # Filter safety
                
                color_scale = "RdYlGn" if view_mode == "Percentage (%) Coverage" else "Blues"
                map_title = f"Geospatial View: Average {y_axis_label}"
                
                fig_map = px.scatter_mapbox(
                    map_df, lat="Lat", lon="Lon", hover_name="Area", 
                    hover_data={"Lat": False, "Lon": False, "Rank_Metric": ':.1f'},
                    color="Rank_Metric", size="Rank_Metric",
                    color_continuous_scale=color_scale,
                    size_max=20, zoom=8.5, center={"lat": 17.55, "lon": 120.75},
                    mapbox_style="carto-positron", title=map_title
                )
                fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig_map, use_container_width=True)
                
                # --- MONTHLY TREND LINE CHART ---
                st.markdown("---")
                st.markdown(f"#### 📉 Monthly Trend Analysis")
                
                trend_agg = filtered_df.groupby('Month')[selected_cols].sum().reset_index()
                months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                trend_agg['Month'] = pd.Categorical(trend_agg['Month'], categories=months_order, ordered=True)
                trend_agg = trend_agg.sort_values('Month')
                
                trend_chart_df = pd.DataFrame({'Month': trend_agg['Month']})
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    for col in selected_cols:
                        trend_chart_df[col] = [(v / provincial_elig * 100) if provincial_elig > 0 else 0 for v in trend_agg[col]]
                        trend_chart_df[col] = trend_chart_df[col].round(1)
                    y_trend_label = "Coverage (%)"
                else:
                    for col in selected_cols:
                        trend_chart_df[col] = trend_agg[col]
                    y_trend_label = "Number of Children"
                
                trend_melted = trend_chart_df.melt(id_vars='Month', value_vars=selected_cols, var_name='Vaccine/Antigen', value_name='Count')
                trend_melted['Vaccine/Antigen'] = trend_melted['Vaccine/Antigen'].str.replace(f"_{gender}", "")
                
                fig_trend = px.line(trend_melted, x='Month', y='Count', color='Vaccine/Antigen', markers=True,
                                    title=f"Provincial Monthly Trend ({start_m} - {end_m})",
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
                
                if view_mode == "Percentage (%) Coverage" and elig_cols:
                    fig_trend.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="DOH Target (95%)")
                    
                fig_trend.update_layout(xaxis_title="Month", yaxis_title=y_trend_label, legend_title="Antigen", margin=dict(t=40))
                st.plotly_chart(fig_trend, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'Abra_Trend_{safe_filename}', 'scale': 4}})

            else:
                st.info("👆 Please select at least one indicator from the dropdown above to view the charts.")
            
            dose_1_col = next((c for c in cols_to_plot if " 1" in c or "1_" in c), None)
            dose_last_col = next((c for c in cols_to_plot if " 3" in c or "3_" in c), next((c for c in cols_to_plot if " 2" in c and "MMR" in c), None))

            if dose_1_col and dose_last_col and tab_title != "Birth Doses":
                st.markdown("---")
                st.markdown(f"#### ⚠️ Dropout Analysis ({dose_1_col.replace(f'_{gender}', '')} to {dose_last_col.replace(f'_{gender}', '')})")
                
                drop_df = agg_df[['Area', dose_1_col, dose_last_col]].copy()
                drop_df['Dropout Rate (%)'] = np.where(drop_df[dose_1_col] > 0, ((drop_df[dose_1_col] - drop_df[dose_last_col]) / drop_df[dose_1_col]) * 100, 0)
                drop_df['Dropout Rate (%)'] = drop_df['Dropout Rate (%)'].round(1)
                
                fig_drop = px.bar(drop_df, x='Area', y='Dropout Rate (%)',
                                  text_auto=True, color='Dropout Rate (%)',
                                  color_continuous_scale=["lightgreen", "yellow", "red"],
                                  title="Highlighting RHUs with high dropout rates from first to final dose.")
                
                fig_drop.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Warning Threshold (10%)")
                fig_drop.update_layout(xaxis_title="Rural Health Unit (RHU)", yaxis_title="Dropout Rate (%)", margin=dict(t=40))
                
                st.plotly_chart(fig_drop, use_container_width=True, config={'toImageButtonOptions': {'filename': f'Abra_Dropout_{safe_filename}', 'scale': 4}})
            
        else:
            st.warning("Could not find graphing columns for the selected demographic.")
            
        with st.expander("📄 View & Download Filtered Data"):
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=f"Abra_{safe_filename}_Data_{start_m}_to_{end_m}.csv", mime="text/csv")
    else:
        st.info("No data uploaded yet. Please go to the Data Uploader page to add your files.")

# --- MAIN DASHBOARD PAGE ---
if page == "📊 Dashboard":
    st.title("💉 Child Immunization Dashboard - Abra Province")
    
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        time_view = st.radio("⏳ Time Aggregation", ["Monthly", "Quarterly"], horizontal=True)
    with col_t2:
        if time_view == "Monthly":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            start_month, end_month = st.select_slider("Select Range", options=months, value=("Jan", "Dec"))
        else:
            quarters = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
            start_q, end_q = st.select_slider("Select Range", options=quarters, value=("Q1 (Jan-Mar)", "Q4 (Oct-Dec)"))
            q_map = {"Q1 (Jan-Mar)": ("Jan", "Mar"), "Q2 (Apr-Jun)": ("Apr", "Jun"), "Q3 (Jul-Sep)": ("Jul", "Sep"), "Q4 (Oct-Dec)": ("Oct", "Dec")}
            start_month = q_map[start_q][0]
            end_month = q_map[end_q][1]
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👶 Birth Doses (BCG/HepB)", 
        "🛡️ Penta (DPT-HiB-HepB)", 
        "💧 Polio (OPV/IPV)", 
        "🫁 Pneumococcal (PCV)", 
        "🎯 MMR, FIC & CIC"
    ])
    
    with tab1:
        render_tab_content("Birth Doses", "CPAB_BCG_HepB", ["CPAB", "BCG", "Hep"], start_month, end_month, gender_filter, selected_year)

    with tab2:
        render_tab_content("Pentavalent", "Penta", ["DPT-HiB-HepB 1", "DPT-HiB-HepB 2", "DPT-HiB-HepB 3", "Penta 1", "Penta 2", "Penta 3"], start_month, end_month, gender_filter, selected_year)

    with tab3:
        render_tab_content("Polio", "Polio", ["OPV 1", "OPV 2", "OPV 3", "IPV 1", "IPV 2"], start_month, end_month, gender_filter, selected_year)

    with tab4:
        render_tab_content("Pneumococcal", "PCV", ["PCV 1", "PCV 2", "PCV 3"], start_month, end_month, gender_filter, selected_year)

    with tab5:
        render_tab_content("MMR, FIC and CIC", "MMR", ["MMR 1", "MMR 2", "13-23", "FIC", "CIC"], start_month, end_month, gender_filter, selected_year)

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    
    admin_password = st.text_input("Enter Admin Password", type="password")
    if admin_password != st.secrets.get("admin_password", "AbraAdmin2026"):
        st.warning("🔒 This section is restricted. Please enter the password to unlock the uploader.")
        st.stop()
        
    st.markdown("Upload your FHSIS Excel files here. The app extracts all 12 monthly sheets, filters for Abra's 27 RHUs, and saves them to Google Sheets.")
    
    upload_year = st.selectbox("📅 Select Year for these uploads (Important for historical tracking):", [2025, 2026, 2027])
    
    col1, col2 = st.columns(2)
    with col1:
        file_cpab = st.file_uploader("Upload: 1 CPAB, BCG and Hepa B", type=["csv", "xlsx"])
        if file_cpab:
            df = load_and_clean_fhsis_data(file_cpab, upload_year)
            if df is not None: st.session_state['fhsis_data']["CPAB_BCG_HepB"] = df
            
        file_penta = st.file_uploader("Upload: 2 DPT-HiB-HepB", type=["csv", "xlsx"])
        if file_penta:
            df = load_and_clean_fhsis_data(file_penta, upload_year)
            if df is not None: st.session_state['fhsis_data']["Penta"] = df
            
        file_polio = st.file_uploader("Upload: 3 OPV and IPV", type=["csv", "xlsx"])
        if file_polio:
            df = load_and_clean_fhsis_data(file_polio, upload_year)
            if df is not None: st.session_state['fhsis_data']["Polio"] = df
            
    with col2:
        file_pcv = st.file_uploader("Upload: 4 PCV", type=["csv", "xlsx"])
        if file_pcv:
            df = load_and_clean_fhsis_data(file_pcv, upload_year)
            if df is not None: st.session_state['fhsis_data']["PCV"] = df
            
        file_mmr = st.file_uploader("Upload: 5 MMR, FIC and CIC", type=["csv", "xlsx"])
        if file_mmr:
            df = load_and_clean_fhsis_data(file_mmr, upload_year)
            if df is not None: st.session_state['fhsis_data']["MMR"] = df
            
    st.markdown("---")
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("☁️ Save Data to Google Sheets", type="primary", use_container_width=True):
            if st.session_state['fhsis_data']:
                save_data_to_gsheets(st.session_state['fhsis_data'])
                st.success(f"✅ {upload_year} Files processed and safely saved to Google Sheets! Head over to the Dashboard.")
            else:
                st.error("No data uploaded yet to save.")
                
    with action_col2:
        if st.button("🗑️ Clear Current Uploads", type="secondary", use_container_width=True):
            clear_session_data()
            st.warning("Current app data cleared. (Note: This does not delete the permanent data inside Google Sheets).")
            st.rerun()
