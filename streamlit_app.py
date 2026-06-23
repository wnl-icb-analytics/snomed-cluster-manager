# =============================================================================
# SNOMED Cluster Manager - Main Application Entry Point
# =============================================================================

import streamlit as st
import pandas as pd
from config import PAGE_CONFIG, CUSTOM_CSS
from database import get_connection, rerun
from services.cluster_service import get_all_clusters
from components.cluster_components import render_flash_message

# Configure the page
st.set_page_config(**PAGE_CONFIG)

# Apply custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Initialize database connection
conn = get_connection()

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

# Initialize session state for navigation
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'selected_cluster' not in st.session_state:
    st.session_state.selected_cluster = None
if 'selected_source' not in st.session_state:
    st.session_state.selected_source = None

# =============================================================================
# MAIN APPLICATION HEADER
# =============================================================================

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🧬 SNOMED Cluster Manager")
    st.markdown("**Manage SNOMED ECL clusters and cached code sets**")

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🧪 Playground", use_container_width=True):
            st.session_state.page = 'playground'
            rerun()
    with col_btn2:
        if st.button("✨ Add New", use_container_width=True, type="primary"):
            st.session_state.page = 'create'
            rerun()

# Load cluster data with error handling
try:
    clusters_df = get_all_clusters()
except Exception as e:
    st.error(f"⚠️ Database connection error: {str(e)}")
    st.info("Please refresh the page or contact support if this persists.")
    clusters_df = pd.DataFrame()

# =============================================================================
# PAGE ROUTING
# =============================================================================

if st.session_state.page == 'home':
    from page_modules.home import render_home
    render_home()

elif st.session_state.page == 'details':
    from page_modules.details import render_details
    render_details()

elif st.session_state.page == 'analytics':
    from page_modules.analytics import render_analytics
    render_analytics()

elif st.session_state.page == 'playground':
    from page_modules.playground import render_playground
    render_playground()

elif st.session_state.page == 'create':
    from page_modules.create import render_create
    render_create()

elif st.session_state.page == 'edit':
    from page_modules.edit import render_edit
    render_edit()

elif st.session_state.page == 'demographics':
    from page_modules.demographics import render_demographics
    render_demographics()
