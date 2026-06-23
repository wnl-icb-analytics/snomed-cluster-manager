# =============================================================================
# SNOMED Cluster Manager - Cluster Details Page
# =============================================================================

import streamlit as st
import pandas as pd
import time
from database import rerun
from services.cluster_service import get_all_clusters, get_cluster_cache, refresh_cluster, delete_cluster
from services.analytics_service import get_observation_analytics, get_distinct_persons_obs, get_observation_time_series, get_cluster_demographics, get_cluster_age_sex_distribution, get_cluster_standardized_rates
from components.cluster_components import render_flash_message, render_change_history
from components.chart_components import create_practice_scatter, create_org_bar_chart
from utils.helpers import format_time_ago, format_ecl_for_display
from utils.charts import create_population_pyramid
from services.codeset_service import is_authored, get_codeset_meta, get_codeset_codes, source_label
from config import CLUSTER_TYPE_DISPLAY, DB_SCHEMA


def render_details():
    """Render the Cluster Details page"""
    if not st.session_state.selected_cluster:
        st.error("No cluster selected")
        st.session_state.page = 'home'
        rerun()
    
    cluster_id = st.session_state.selected_cluster
    source = st.session_state.get('selected_source')

    # Brought-in codesets are read-only and rendered separately
    if not is_authored(source):
        render_external_details(cluster_id, source)
        return

    # Get cluster info
    clusters_df = get_all_clusters()
    cluster_info = clusters_df[clusters_df['CLUSTER_ID'] == cluster_id]
    if cluster_info.empty:
        st.error(f"Cluster '{cluster_id}' not found")
        st.session_state.page = 'home'
        rerun()
    
    cluster = cluster_info.iloc[0]
    
    # Header with back button
    col1, col2, col3 = st.columns([1, 6, 2])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = 'home'
            rerun()
    with col3:
        if st.button("✏️ Edit", use_container_width=True, type="primary"):
            st.session_state.page = 'edit'
            rerun()
    
    # Title on separate row to allow proper wrapping
    st.title(f"📋 {cluster_id}")
    
    # Type in normal text, description in italics
    type_display = CLUSTER_TYPE_DISPLAY.get(cluster.get('CLUSTER_TYPE', 'OBSERVATION'), '[observation]')
    if cluster.get('DESCRIPTION'):
        st.markdown(f"{type_display} • *{cluster.get('DESCRIPTION')}*")
    else:
        st.markdown(f"{type_display}")
    
    # Flash message component
    render_flash_message()
    
    # Action buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Refresh Cache", use_container_width=True):
            with st.spinner("Refreshing cluster cache..."):
                result = refresh_cluster(cluster_id, force=True)
                if "SUCCESS" in str(result):
                    st.session_state["flash"] = ("success", "✅ Cache refreshed successfully!")
                else:
                    st.session_state["flash"] = ("error", f"❌ Refresh failed: {result}")
            rerun()
    
    with col2:
        if st.button("🧪 Test ECL", use_container_width=True):
            if cluster['ECL_EXPRESSION']:
                st.session_state["ecl_test_expr"] = cluster['ECL_EXPRESSION']
                st.session_state.page = 'playground'
                rerun()
            else:
                st.warning("No ECL expression to test.")
    
    with col3:
        if st.button("📈 Analytics", use_container_width=True):
            st.session_state.page = 'analytics'
            rerun()
    
    with col4:
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state["confirm_delete"] = cluster_id
            rerun()
    
    # ECL Expression display
    st.subheader("🧬 ECL Expression")
    if cluster['ECL_EXPRESSION']:
        formatted_ecl = format_ecl_for_display(cluster['ECL_EXPRESSION'])
        st.code(formatted_ecl, language='go')
    else:
        st.warning("No ECL expression defined for this cluster.")
    
    # Confirmation dialog for delete
    if st.session_state.get("confirm_delete") == cluster_id:
        st.warning(f"⚠️ **Are you sure you want to delete cluster '{cluster_id}'?**")
        st.markdown("This action cannot be undone. All cached codes and history will be permanently deleted.")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col2:
            if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                if delete_cluster(cluster_id):
                    st.session_state["flash"] = ("success", f"✅ Cluster '{cluster_id}' deleted successfully!")
                    st.session_state.page = 'home'
                    st.session_state.selected_cluster = None
                    # Clear cached database connection to ensure fresh queries
                    try:
                        from database import get_connection
                        get_connection.clear()
                    except:
                        pass  # Ignore errors if cache doesn't exist
                if "confirm_delete" in st.session_state:
                    del st.session_state["confirm_delete"]
                rerun()
        
        with col3:
            if st.button("❌ Cancel", use_container_width=True):
                if "confirm_delete" in st.session_state:
                    del st.session_state["confirm_delete"]
                rerun()
    
    # Cluster info as KPI strip
    cache_df = get_cluster_cache(cluster_id)
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        if not cache_df.empty:
            st.metric("Total Codes", f"{len(cache_df):,}")
        else:
            st.metric("Total Codes", "0")
    
    with kpi_col2:
        if not cache_df.empty and 'LAST_REFRESHED' in cache_df.columns:
            last_refresh = cache_df['LAST_REFRESHED'].max()
            st.metric("Last Refreshed", format_time_ago(last_refresh))
        else:
            st.metric("Last Refreshed", "Never")
    
    with kpi_col3:
        st.metric("Created", format_time_ago(cluster.get('CREATED_AT')))
    
    with kpi_col4:
        # Use correct field name for last updated
        updated_time = cluster.get('UPDATED_AT') or cluster.get('CREATED_AT')
        st.metric("Last Updated", format_time_ago(updated_time))
    
    if cache_df.empty:
        st.info("No cached codes found. Try refreshing the cache.")
    else:
        # Search codes
        code_search = st.text_input("🔍 Search codes", placeholder="Search by code or description...")
        
        # Filter codes
        filtered_df = cache_df
        if code_search:
            mask = (cache_df['CODE'].astype(str).str.contains(code_search, case=False, na=False) | 
                   cache_df['DISPLAY'].str.contains(code_search, case=False, na=False))
            filtered_df = cache_df[mask]
        
        if not filtered_df.empty:
            # Display codes
            display_df = filtered_df[['CODE', 'DISPLAY']].copy()
            st.dataframe(display_df, use_container_width=True)
            
            if len(filtered_df) < len(cache_df):
                st.caption(f"Showing {len(filtered_df)} of {len(cache_df)} codes")
        else:
            st.info(f"No codes match '{code_search}'")
    
    # SQL query section
    if cluster['ECL_EXPRESSION']:
        st.subheader("💻 SQL Query")
        st.markdown("Copy this query to get all SNOMED codes in this cluster:")
        sql_query = f"""-- Get all SNOMED codes in cluster {cluster_id}
SELECT 
    code,
    display,
    system
FROM {DB_SCHEMA}.ecl_cache
WHERE cluster_id = '{cluster_id}'
ORDER BY code;"""
        st.code(sql_query, language='sql')
    
    # Change history
    render_change_history(cluster_id, cluster)


def render_external_details(cluster_id, source):
    """Details page for a brought-in (read-only) codeset from COMBINED_CODESETS."""
    meta = get_codeset_meta(cluster_id, source)
    if meta.empty:
        st.error(f"Codeset '{cluster_id}' not found in {source_label(source)}")
        st.session_state.page = 'home'
        rerun()

    info = meta.iloc[0]

    # Header
    col1, col2, col3 = st.columns([1, 6, 2])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = 'home'
            rerun()
    with col3:
        if st.button("📈 Analytics", use_container_width=True, type="primary"):
            st.session_state.page = 'analytics'
            rerun()

    st.title(f"📋 {cluster_id}")
    st.markdown(f"📥 **{source_label(source)}** (brought-in, read-only)")
    if info.get('DESCRIPTION'):
        st.markdown(f"*{info.get('DESCRIPTION')}*")

    # Analysis mode - brought-in codesets have no stored type, so the user picks
    modes = ['OBSERVATION', 'MEDICATION']
    current = st.session_state.get('codeset_mode', 'OBSERVATION')
    mode = st.radio(
        "Analysis mode", options=modes,
        index=modes.index(current) if current in modes else 0,
        horizontal=True,
        help="Brought-in codesets can mix clinical and medication codes - choose how to analyse them",
        format_func=lambda m: "🩺 Observation" if m == 'OBSERVATION' else "💊 Medication"
    )
    st.session_state['codeset_mode'] = mode

    # Member codes
    code_count = int(info.get('CODE_COUNT') or 0)
    st.metric("Member codes", f"{code_count:,}")

    codes_df = get_codeset_codes(cluster_id, source)
    if codes_df.empty:
        st.info("No member codes found for this codeset.")
        return

    code_search = st.text_input("🔍 Search codes", placeholder="Search by code or description...")
    filtered = codes_df
    if code_search:
        mask = (codes_df['CODE'].astype(str).str.contains(code_search, case=False, na=False) |
                codes_df['DISPLAY'].astype(str).str.contains(code_search, case=False, na=False))
        filtered = codes_df[mask]

    if filtered.empty:
        st.info(f"No codes match '{code_search}'")
    else:
        st.dataframe(filtered, use_container_width=True)
        if len(filtered) < len(codes_df):
            st.caption(f"Showing {len(filtered)} of {len(codes_df)} codes")

    # SQL template
    st.subheader("💻 SQL Query")
    sql_query = f"""-- Get all codes in codeset {cluster_id} ({source_label(source)})
SELECT code, code_description, source
FROM {DB_SCHEMA}.combined_codesets
WHERE cluster_id = '{cluster_id}'
  AND source = '{source}'
ORDER BY code;"""
    st.code(sql_query, language='sql')