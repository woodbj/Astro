import streamlit as st
import pandas as pd
import numpy as np

localhost = "192.168.86.139"

# Page config
st.set_page_config(page_title="Layout Demo", layout="wide")

# Title
st.title("Streamlit Layout Features")

# Sidebar
with st.sidebar:
    st.header("Sidebar")
    option = st.selectbox("Select option", ["Option 1", "Option 2", "Option 3"])
    slider_val = st.slider("Slider", 0, 100, 50)

# Columns
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Metric 1", "1,234", "+12%")

with col2:
    st.metric("Metric 2", "5,678", "-3%")

with col3:
    st.metric("Metric 3", "9,012", "+8%")

# Tabs
tab1, tab2, tab3 = st.tabs(["Chart", "Data", "Info"])

with tab1:
    st.subheader("Sample Chart")
    chart_data = pd.DataFrame(np.random.randn(20, 3), columns=["A", "B", "C"])
    st.line_chart(chart_data)

with tab2:
    st.subheader("Sample Data")
    st.dataframe(chart_data)

with tab3:
    st.subheader("Information")
    st.write("This dashboard demonstrates key Streamlit layout features.")

# Expander
with st.expander("Click to expand"):
    st.write("Hidden content inside expander")
    st.code("print('Hello World')")

# Container
with st.container():
    st.subheader("Container Section")
    left, right = st.columns(2)
    left.write("Left column content")
    right.write("Right column content")
