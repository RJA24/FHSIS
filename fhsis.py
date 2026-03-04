import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FHSIS Immunization Dashboard", page_icon="💉", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Department_of_Health_%28Philippines%29_Seal.png/600px-Department_of_Health_%28Philippines%29_Seal.png", width=100)
    st.title("FHSIS App")
    
    # Page Navigation
    page = st.radio("Navigation", ["📊 Dashboard", "📁 Data Uploader", "ℹ️ About"])
    
    st.markdown("---")
    
    # Global Filters
    if page == "📊 Dashboard":
        st.subheader("Global Filters")
        
        # Dropdown selector for Gender as requested
        gender_filter = st.selectbox(
            "Select Demographic",
            options=["Total", "Male", "Female"],
            help="This selection applies to all indicators in the dashboard."
        )
        
        # Optional: Area Filter (Very useful for DOH vs RHU views)
        area_filter = st.selectbox(
            "Select Area / Municipality",
            options=["All of CAR", "Abra", "Bangued", "Bucay", "Dolores"],
            help="Filter data by specific region or municipality."
        )

# --- MAIN DASHBOARD PAGE ---
if page == "📊 Dashboard":
    st.title("💉 Child Immunization Dashboard")
    st.markdown("Monitor health outcomes, vaccine coverage, and fully immunized children across the region.")
    
    # Range Slider for Months at the top of the page
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    start_month, end_month = st.select_slider(
        "Select Month Range",
        options=months,
        value=("Jan", "Dec")
    )
    
    st.info(f"Currently displaying data for **{gender_filter}** population from **{start_month} to {end_month}** in **{area_filter}**.")
    
    # --- TABS FOR INDICATORS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👶 Birth Doses (BCG/HepB)", 
        "🛡️ Penta (DPT-HiB-HepB)", 
        "💧 Polio (OPV/IPV)", 
        "🫁 Pneumococcal (PCV)", 
        "🎯 MMR & FIC"
    ])
    
    # Mock data generation for layout presentation
    municipalities = ["Bangued", "Bucay", "Dolores", "La Paz", "Manabo"]
    
    with tab1:
        st.header("CPAB, BCG, and Hepa B Coverage")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total CPAB", "1,204", "+5% from last period")
        col2.metric("BCG (0-28 days)", "3,450", "+12%")
        col3.metric("HepB (Within 24hrs)", "3,100", "-2%")
        
        # Outline of Chart: Grouped Bar Chart
        st.subheader("BCG vs HepB Administration by Municipality")
        mock_df1 = pd.DataFrame({
            "Municipality": municipalities,
            "BCG": np.random.randint(100, 500, 5),
            "HepB": np.random.randint(100, 480, 5)
        })
        fig1 = px.bar(mock_df1, x="Municipality", y=["BCG", "HepB"], barmode="group", 
                      color_discrete_sequence=["#1f77b4", "#ff7f0e"])
        st.plotly_chart(fig1, use_container_width=True)
        
        st.dataframe(mock_df1, use_container_width=True)

    with tab2:
        st.header("Pentavalent Vaccine (DPT-HiB-HepB)")
        st.markdown("Track the drop-off rates between Dose 1, Dose 2, and Dose 3.")
        
        # Outline of Chart: Funnel / Drop off
        mock_penta = pd.DataFrame(dict(
            number=[4000, 3200, 2800],
            stage=["Dose 1", "Dose 2", "Dose 3"]
        ))
        fig2 = px.funnel(mock_penta, x='number', y='stage', title="Pentavalent Retention Funnel")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.header("Polio Vaccines (OPV & IPV)")
        # Outline of Chart: Line Trend
        st.subheader(f"OPV 1, 2, 3 Trends ({start_month} - {end_month})")
        mock_months = months[months.index(start_month) : months.index(end_month)+1]
        mock_opv = pd.DataFrame({
            "Month": mock_months,
            "OPV 1": np.random.randint(500, 800, len(mock_months)),
            "OPV 2": np.random.randint(400, 700, len(mock_months)),
            "OPV 3": np.random.randint(300, 600, len(mock_months))
        })
        fig3 = px.line(mock_opv, x="Month", y=["OPV 1", "OPV 2", "OPV 3"], markers=True)
        st.plotly_chart(fig3, use_container_width=True)

    with tab4:
        st.header("Pneumococcal Conjugate Vaccine (PCV)")
        st.subheader("PCV 3 Completion Rates")
        
        # Outline of Chart: Horizontal Bar
        mock_pcv = pd.DataFrame({
            "Municipality": municipalities,
            "PCV 3 Given": np.random.randint(200, 600, 5)
        }).sort_values("PCV 3 Given", ascending=True)
        
        fig4 = px.bar(mock_pcv, x="PCV 3 Given", y="Municipality", orientation='h', color="PCV 3 Given", color_continuous_scale="Teal")
        st.plotly_chart(fig4, use_container_width=True)

    with tab5:
        st.header("Measles, FIC, and CIC")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Fully Immunized Children (FIC)")
            # Outline of Chart: Donut Chart
            fig5 = px.pie(values=[75, 25], names=["Fully Immunized", "Pending/Missed"], hole=0.6, 
                          color_discrete_sequence=["#2ca02c", "#d62728"])
            fig5.update_traces(textinfo='percent+label')
            st.plotly_chart(fig5, use_container_width=True)
            
        with col2:
            st.subheader("MMR 1 vs MMR 2 Drop-outs")
            mock_mmr = pd.DataFrame({
                "Vaccine": ["MMR 1", "MMR 2"],
                "Count": [3500, 2900]
            })
            fig6 = px.bar(mock_mmr, x="Vaccine", y="Count", text="Count", color="Vaccine")
            st.plotly_chart(fig6, use_container_width=True)

# --- DATA UPLOADER PAGE ---
elif page == "📁 Data Uploader":
    st.title("Secure Data Uploader")
    st.markdown("RHU Personnel: Upload your updated monthly FHSIS Excel/CSV files here to update the dashboard metrics.")
    
    indicator_type = st.selectbox(
        "Select the indicator data you are uploading:",
        ["CPAB, BCG and Hepa B", "DPT-HiB-HepB", "OPV and IPV", "PCV", "MMR, FIC and CIC"]
    )
    
    uploaded_file = st.file_uploader(f"Upload File for {indicator_type}", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        st.success(f"Successfully uploaded {uploaded_file.name}!")
        with st.expander("Preview Uploaded Data"):
            try:
                # Basic preview assuming CSV for now
                df = pd.read_csv(uploaded_file, skiprows=4)
                st.dataframe(df.head())
            except:
                st.write("File uploaded, but could not read preview format automatically.")
                
        st.button("Process & Update Dashboard")

# --- ABOUT PAGE ---
elif page == "ℹ️ About":
    st.title("About this System")
    st.markdown("""
    This Child Immunization Dashboard was built to streamline the tracking of health metrics for the Field Health Services Information System (FHSIS).
    
    **Features:**
    * **Interactive Indicators:** Real-time calculation of vaccination rates.
    * **Granular Filtering:** Filter by time intervals (months) and demographics (Gender).
    * **Actionable Insights:** Easily identify drop-out rates between Dose 1 and Dose 3 of multi-dose vaccines.
    """)
