# =============================================================================
# SNOMED Cluster Manager - Analytics Page
# =============================================================================

import streamlit as st
import pandas as pd
import time
from database import rerun
from services.cluster_service import get_all_clusters, get_cluster_cache, refresh_cluster
from services.analytics_service import (
    get_observation_analytics, get_medication_analytics, get_distinct_persons_obs, 
    get_distinct_persons_med, get_observation_time_series, get_medication_time_series,
    get_cluster_demographics, get_cluster_age_sex_distribution, get_cluster_standardized_rates,
    get_cluster_ethnicity_analysis, get_cluster_deprivation_analysis, 
    get_cluster_language_analysis, get_cluster_neighbourhood_analysis
)
from components.chart_components import create_practice_scatter, create_org_bar_chart
from utils.charts import (
    create_population_pyramid, create_age_slope_chart, create_ethnicity_bar_chart,
    create_deprivation_bar_chart, create_language_bar_chart, create_neighbourhood_bar_chart
)
from services.codeset_service import is_authored, get_codeset_meta, get_codeset_codes, source_label
from config import DB_ANALYTICS, DB_SCHEMA, DB_STORE, DB_DEMOGRAPHICS


def render_analytics():
    """Render the Analytics page"""
    if not st.session_state.selected_cluster:
        st.error("No cluster selected")
        st.session_state.page = 'home'
        rerun()
    
    cluster_id = st.session_state.selected_cluster
    source = st.session_state.get('selected_source')
    authored = is_authored(source)

    # Header with back button
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = 'details'
            rerun()
    
    st.title(f"📈 Analytics: {cluster_id}")
    
    # Resolve cluster type and code count for authored clusters or brought-in codesets
    if authored:
        clusters_df = get_all_clusters()
        cluster_info = clusters_df[clusters_df['CLUSTER_ID'] == cluster_id]
        if cluster_info.empty:
            st.error(f"Cluster '{cluster_id}' not found")
            st.session_state.page = 'home'
            rerun()
        cluster = cluster_info.iloc[0]
        cluster_type = cluster.get('CLUSTER_TYPE', 'OBSERVATION')
        record_count = cluster.get('RECORD_COUNT')
    else:
        meta = get_codeset_meta(cluster_id, source)
        if meta.empty:
            st.error(f"Codeset '{cluster_id}' not found")
            st.session_state.page = 'home'
            rerun()
        # Mode is chosen on the details page and carried here (no re-selection)
        cluster_type = st.session_state.get('codeset_mode', 'OBSERVATION')
        record_count = int(meta.iloc[0]['CODE_COUNT'] or 0)

    # Consistent subtitle: mode badge for everyone, source prefix for brought-in
    mode_badge = "🩺 Observation" if cluster_type == 'OBSERVATION' else "💊 Medication"
    if authored:
        st.markdown(mode_badge)
    else:
        st.markdown(f"📥 **{source_label(source)}** · {mode_badge}")
        st.caption("Mode is set on the codeset's details page")

    def cluster_member_codes():
        """All member codes for this codeset: authored cache or brought-in source."""
        return get_cluster_cache(cluster_id) if authored else get_codeset_codes(cluster_id, source)

    # SQL-template building blocks: authored clusters live in ecl_cache, brought-in
    # codesets live in combined_codesets (filtered by source).
    if authored:
        tmpl_code_join = f"{DB_SCHEMA}.ecl_cache ec"
        tmpl_code_where = f"ec.cluster_id = '{cluster_id}'"
        tmpl_codes_query = f"""-- Get all codes in cluster {cluster_id}
SELECT code, display, system
FROM {DB_SCHEMA}.ecl_cache
WHERE cluster_id = '{cluster_id}'
ORDER BY code;"""
    else:
        tmpl_code_join = f"{DB_SCHEMA}.combined_codesets ec"
        tmpl_code_where = f"ec.cluster_id = '{cluster_id}' AND ec.source = '{source}'"
        tmpl_codes_query = f"""-- Get all codes in codeset {cluster_id} ({source})
SELECT code, code_description, source
FROM {DB_SCHEMA}.combined_codesets
WHERE cluster_id = '{cluster_id}' AND source = '{source}'
ORDER BY code;"""

    # Authored clusters can be empty before first refresh; brought-in always have codes
    if authored and (not record_count or record_count == 0):
        st.warning("⚠️ This cluster has no cached codes. Please refresh the cluster first.")
        if st.button("🔄 Refresh Cluster Now"):
            result = refresh_cluster(cluster_id, force=True)
            if result.startswith("SUCCESS"):
                st.success(f"✅ {result}")
                time.sleep(1)
                rerun()
            else:
                st.error(f"❌ {result}")
    else:
        # Create tabs based on cluster type
        if cluster_type == 'OBSERVATION':
            tabs = st.tabs(["📊 Overview", "📄 Code Usage", "👥 Age/Sex", "🏥 Organisation Counts", "⚖️ Health Equity", "💻 SQL Templates"])
        elif cluster_type == 'MEDICATION':
            tabs = st.tabs(["💊 Overview", "📄 Code Usage", "👥 Age/Sex", "🏥 Care Teams", "⚖️ Health Equity", "💻 SQL Templates"])
        else:
            # Default to observation if type is unknown
            tabs = st.tabs(["📊 Overview", "📄 Code Usage", "👥 Demographics", "⚖️ Health Equity", "💻 SQL Templates"])
            cluster_type = 'OBSERVATION'
        
        # Load data based on cluster type
        if cluster_type == 'OBSERVATION':
            # Tab 1: Overview
            with tabs[0]:
                st.subheader("📊 Usage Summary")
                st.markdown("Summary statistics for all observations in this cluster")
                
                with st.spinner("Loading observation data..."):
                    obs_df = get_observation_analytics(cluster_id, source=source)
                    total_persons, active_persons, total_observations = get_distinct_persons_obs(cluster_id, source=source)
                if not obs_df.empty:
                    # Get total cluster codes for comparison
                    cluster_codes = cluster_member_codes()
                    total_codes_in_cluster = len(cluster_codes) if not cluster_codes.empty else 0
                    unused_codes = total_codes_in_cluster - len(obs_df)
                    
                    # Overview metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Persons Ever Coded (Active / Total)",
                            f"{active_persons:,} / {total_persons:,}"
                        )
                    with col2:
                        st.metric("Total Observations", f"{total_observations:,}")
                    with col3:
                        avg_per_person = total_observations / active_persons if active_persons > 0 else 0
                        st.metric("Avg per Person", f"{avg_per_person:.1f}")
                    with col4:
                        st.metric("Codes with Usage", f"{len(obs_df)}/{total_codes_in_cluster}")
                    
                    # Show unused codes warning if any
                    if unused_codes > 0:
                        st.warning(f"⚠️ {unused_codes} code(s) in this cluster have never been used in observations")
                    
                    # Usage over time chart integrated into overview  
                    st.subheader("📈 Usage Over Time (Last 5 Years)")
                    time_df = get_observation_time_series(cluster_id, source=source)
                    
                    if not time_df.empty:
                        st.markdown("**Observations per Month:**")
                        if 'MONTH_YEAR' not in time_df.columns or not pd.api.types.is_datetime64_any_dtype(time_df['MONTH_YEAR']):
                            time_df['MONTH_YEAR'] = pd.to_datetime(time_df['MONTH_YEAR'])
                        chart_df = time_df.set_index('MONTH_YEAR')['OBSERVATION_COUNT']
                        st.line_chart(chart_df, height=400)
                    else:
                        st.info("No observation data found")
                else:
                    st.info("No observation data found for these codes - none have ever been used in patient records.")
            
            # Tab 2: Code Usage
            with tabs[1]:
                st.subheader("📋 Code Usage Analysis")
                st.markdown("Ranking of codes by usage frequency and patient reach")
                
                with st.spinner("Loading code usage data..."):
                    obs_df = get_observation_analytics(cluster_id, source=source)
                
                # Get cluster codes for analysis
                cluster_codes = cluster_member_codes()
                total_codes_in_cluster = len(cluster_codes) if not cluster_codes.empty else 0
                used_codes = len(obs_df) if not obs_df.empty else 0
                unused_codes = total_codes_in_cluster - used_codes
                
                # Code-level breakdown (only show if we have data)
                if not obs_df.empty:
                    st.caption("Ranked by patient reach - shows only codes that have been recorded at least once")
                    st.dataframe(
                        obs_df[['CODE', 'DISPLAY', 'PERSON_COUNT', 'OBSERVATION_COUNT']],
                        use_container_width=True
                    )
                    
                    # Download button
                    csv = obs_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Observation Data",
                        data=csv,
                        file_name=f"{cluster_id}_observation_analytics.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No observation data found for these codes - none have ever been used in patient records.")
                
                # Show unused codes if any
                if unused_codes > 0:
                    st.divider()
                    st.caption(f"**Unused codes:** These {unused_codes} code(s) are in the cluster but have never been recorded")
                    
                    # Get unused codes
                    if not obs_df.empty:
                        used_codes_set = set(obs_df['CODE'].tolist())
                        all_codes_set = set(cluster_codes['CODE'].tolist()) if not cluster_codes.empty else set()
                        unused_codes_set = all_codes_set - used_codes_set
                        
                        if unused_codes_set:
                            unused_display_df = cluster_codes[cluster_codes['CODE'].isin(unused_codes_set)][['CODE', 'DISPLAY']]
                            st.dataframe(unused_display_df, use_container_width=True)
                    else:
                        # All codes are unused
                        st.dataframe(cluster_codes[['CODE', 'DISPLAY']], use_container_width=True)
            
            # Tab 3: Age/Sex
            with tabs[2]:
                st.subheader("👥 Age & Sex Distribution")
                st.markdown("Age and sex breakdown of patients with observations in this cluster")
                
                with st.spinner("Loading demographics data..."):
                    cluster_demographics = get_cluster_demographics(cluster_id, cluster_type, source=source)
                    
                    if not cluster_demographics.empty:
                        summary = cluster_demographics.iloc[0]
                        
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Active Patients", f"{summary['TOTAL_PATIENTS']:,.0f}")
                        with col2:
                            st.metric("Average Age", f"{summary['AVG_AGE']:.1f} years")
                        with col3:
                            male_pct = (summary['MALE_COUNT'] / summary['TOTAL_PATIENTS']) * 100
                            st.metric("Male %", f"{male_pct:.1f}%")
                        with col4:
                            female_pct = (summary['FEMALE_COUNT'] / summary['TOTAL_PATIENTS']) * 100
                            st.metric("Female %", f"{female_pct:.1f}%")
                        
                        # Population pyramid and age distribution charts
                        age_sex_dist = get_cluster_age_sex_distribution(cluster_id, cluster_type, source=source)
                        if not age_sex_dist.empty:
                            create_population_pyramid(age_sex_dist)
                            create_age_slope_chart(age_sex_dist)
                        else:
                            st.warning("No age/sex distribution data available")
                        
                        # Rates analysis moved to Care Teams tab
                    else:
                        st.info("No demographics data available for this cluster.")
            
            # Tab 4: Organisation Counts
            with tabs[3]:
                st.subheader("🏥 Organisation Analysis")
                st.markdown("Patient counts by organisational unit")
                
                with st.spinner("Loading organisation data..."):
                    # Load practice-level data (always needed for scatter plot)
                    practice_rates = get_cluster_standardized_rates(cluster_id, cluster_type, "Practice", source=source)
                    
                    if not practice_rates.empty:
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            total_patients = practice_rates['PATIENTS_WITH_CODE'].sum()
                            st.metric("Total Patients", f"{total_patients:,}")
                        with col2:
                            avg_rate = practice_rates['RATE_PER_1000'].mean()
                            st.metric("Average Rate", f"{avg_rate:.2f} per 1,000")
                        with col3:
                            new_patients = practice_rates['NEW_PATIENTS_30D'].sum()
                            st.metric("New (30 days)", f"{new_patients:,}")
                        with col4:
                            practice_count = len(practice_rates)
                            st.metric("Practices", practice_count)
                        
                        st.divider()
                        
                        # Always show practice scatter plot
                        st.subheader("Practice Distribution")
                        scatter_chart = create_practice_scatter(practice_rates)
                        if scatter_chart:
                            st.altair_chart(scatter_chart, use_container_width=True)
                        
                        # Aggregated view section
                        st.subheader("Aggregated View")
                        
                        # Aggregation level selector for bar chart
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            agg_level = st.selectbox(
                                "Aggregate by:",
                                options=["Borough", "PCN", "Neighbourhood"],
                                index=0,
                                help="Choose aggregation level for bar chart",
                                key="org_agg_level"
                            )
                        
                        # Load and display aggregated data
                        agg_rates = get_cluster_standardized_rates(cluster_id, cluster_type, agg_level, source=source)
                        if not agg_rates.empty:
                            bar_chart = create_org_bar_chart(agg_rates, agg_level)
                            if bar_chart:
                                st.altair_chart(bar_chart, use_container_width=True)
                        
                        # Data table (always visible)
                        st.subheader("Data Table")
                        
                        # Selector for which data to show in table
                        table_view = st.radio(
                            "Show data for:",
                            options=["Practices", agg_level],
                            horizontal=True,
                            key="table_view_selector"
                        )
                        
                        # Display appropriate data
                        if table_view == "Practices":
                            display_df = practice_rates.copy()
                        else:
                            display_df = agg_rates.copy()
                        
                        # Format the dataframe for display
                        display_df['RATE_PER_1000'] = display_df['RATE_PER_1000'].round(2)
                        display_df['AVG_AGE'] = display_df['AVG_AGE'].round(1)
                        
                        # Rename columns for display
                        display_df = display_df.rename(columns={
                            'UNIT_NAME': 'Practice' if table_view == "Practices" else agg_level,
                            'TOTAL_POPULATION': 'Population',
                            'PATIENTS_WITH_CODE': 'Patients',
                            'AVG_AGE': 'Avg Age',
                            'NEW_PATIENTS_30D': 'New (30d)',
                            'RATE_PER_1000': 'Rate/1000'
                        })
                        
                        st.dataframe(display_df, use_container_width=True)
                        
                        # Download button
                        csv = display_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Data",
                            data=csv,
                            file_name=f"rates_{table_view.lower().replace(' ', '_')}_{cluster_id}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No data available")
            
            # Tab 5: Health Equity
            with tabs[4]:
                st.subheader("⚖️ Health Equity Analysis")
                st.markdown("Analysis of health inequalities across different population groups")
                
                with st.spinner("Loading health equity data..."):
                    # Load all equity data
                    ethnicity_data = get_cluster_ethnicity_analysis(cluster_id, cluster_type, source=source)
                    deprivation_data = get_cluster_deprivation_analysis(cluster_id, cluster_type, source=source)
                    language_data = get_cluster_language_analysis(cluster_id, cluster_type, source=source)
                    neighbourhood_data = get_cluster_neighbourhood_analysis(cluster_id, cluster_type, source=source)
                    
                    # Ethnicity Analysis
                    st.subheader("📊 Ethnicity")
                    if not ethnicity_data.empty:
                        create_ethnicity_bar_chart(ethnicity_data)
                    else:
                        st.info("No ethnicity data available")
                    
                    st.divider()
                    
                    # Deprivation Analysis
                    st.subheader("💰 Social Deprivation")
                    if not deprivation_data.empty:
                        create_deprivation_bar_chart(deprivation_data)
                    else:
                        st.info("No deprivation data available")
                    
                    st.divider()
                    
                    # Language Analysis
                    st.subheader("🗣️ Language & Access")
                    if not language_data.empty:
                        create_language_bar_chart(language_data)
                    else:
                        st.info("No language data available")
                    
                    st.divider()
                    
                    # Neighbourhood Analysis
                    st.subheader("🏘️ Neighbourhood Comparison")
                    if not neighbourhood_data.empty:
                        create_neighbourhood_bar_chart(neighbourhood_data)
                    else:
                        st.info("No neighbourhood data available")
            
            # Tab 6: SQL Templates  
            with tabs[5]:
                st.subheader("SQL Query Templates")
                st.markdown("#### 💻 Data Export Queries")
                st.markdown("Copy these queries to extract data from Snowflake. Each query is ready to run - just paste into your SQL editor.")
                
                # Basic codes query
                st.markdown("### Get All Codes in This Cluster")
                query1 = tmpl_codes_query
                st.code(query1, language='sql')
                
                # Patient list query
                st.markdown("### Get Patients with These Observations")
                query2 = f"""-- Get list of patients with observations in cluster {cluster_id}
SELECT DISTINCT
    d.person_id,
    d.practice_name,
    d.age,
    d.gender,
    COUNT(DISTINCT o.id) as observation_count,
    MIN(o.clinical_effective_date) as first_observation,
    MAX(o.clinical_effective_date) as last_observation
FROM {tmpl_code_join}
JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
WHERE {tmpl_code_where}
AND d.is_active = true
GROUP BY d.person_id, d.practice_name, d.age, d.gender
ORDER BY observation_count DESC;"""
                st.code(query2, language='sql')
                
                # Practice summary query
                st.markdown("### Summary by Practice")
                query3 = f"""-- Get practice-level summary for cluster {cluster_id}
SELECT 
    d.practice_name,
    d.pcn_name,
    d.borough_registered,
    COUNT(DISTINCT d.person_id) as patient_count,
    COUNT(DISTINCT o.id) as total_observations,
    ROUND(AVG(d.age), 1) as avg_age,
    COUNT(DISTINCT CASE WHEN o.clinical_effective_date >= DATEADD('day', -30, CURRENT_DATE()) THEN d.person_id END) as recent_patients_30d
FROM {tmpl_code_join}
JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
WHERE {tmpl_code_where}
AND d.is_active = true
GROUP BY d.practice_name, d.pcn_name, d.borough_registered
HAVING patient_count >= 5  -- Privacy threshold
ORDER BY patient_count DESC;"""
                st.code(query3, language='sql')
                
                # Time series query
                st.markdown("### Monthly Trend Analysis")
                query4 = f"""-- Get monthly observation counts for cluster {cluster_id}
SELECT 
    DATE_TRUNC('month', o.clinical_effective_date) as month,
    COUNT(DISTINCT d.person_id) as unique_patients,
    COUNT(DISTINCT o.id) as observation_count
FROM {tmpl_code_join}
JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
WHERE {tmpl_code_where}
AND o.clinical_effective_date >= DATEADD('month', -24, CURRENT_DATE())
AND o.clinical_effective_date < CURRENT_DATE()
GROUP BY DATE_TRUNC('month', o.clinical_effective_date)
ORDER BY month DESC;"""
                st.code(query4, language='sql')
                
                # Demographics breakdown
                st.markdown("### Demographics Analysis")
                query5 = f"""-- Get demographic breakdown for cluster {cluster_id}
SELECT 
    d.age_band_5y,
    d.gender,
    d.ethnicity_category,
    COUNT(DISTINCT d.person_id) as patient_count
FROM {tmpl_code_join}
JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
WHERE {tmpl_code_where}
AND d.is_active = true
GROUP BY d.age_band_5y, d.gender, d.ethnicity_category
ORDER BY d.age_band_5y, d.gender, d.ethnicity_category;"""
                st.code(query5, language='sql')
                
        elif cluster_type == 'MEDICATION':
            with st.spinner("Loading medication data..."):
                med_df = get_medication_analytics(cluster_id, source=source)
            
            # Tab 1: Overview
            with tabs[0]:
                st.subheader("💊 Usage Summary")
                if not med_df.empty:
                    # Get total cluster codes for comparison
                    cluster_codes = cluster_member_codes()
                    total_codes_in_cluster = len(cluster_codes) if not cluster_codes.empty else 0
                    unused_codes = total_codes_in_cluster - len(med_df)
                    
                    # Overview metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        # Get distinct person count across all codes in cluster
                        total_persons, active_persons, total_orders = get_distinct_persons_med(cluster_id, source=source)
                        st.metric(
                            f"Persons Ever Ordered (Active / Total)",
                            f"{active_persons:,} / {total_persons:,}"
                        )
                    with col2:
                        total_orders = med_df['ORDER_COUNT'].sum()
                        st.metric("Total Orders", f"{total_orders:,}")
                    with col3:
                        avg_per_person = total_orders / total_persons if total_persons > 0 else 0
                        st.metric("Avg per Person", f"{avg_per_person:.1f}")
                    with col4:
                        st.metric("Meds with Usage", f"{len(med_df)}/{total_codes_in_cluster}")
                    
                    # Show unused codes warning if any
                    if unused_codes > 0:
                        st.warning(f"⚠️ {unused_codes} medication(s) in this cluster have never been ordered")
                    
                    # Usage over time chart integrated into overview
                    st.subheader("📈 Usage Over Time (Last 5 Years)")
                    time_df = get_medication_time_series(cluster_id, source=source)
                    
                    if not time_df.empty:
                        st.markdown("**Orders per Month:**")
                        time_df['MONTH_YEAR'] = pd.to_datetime(time_df['MONTH_YEAR'])
                        chart_df = time_df.set_index('MONTH_YEAR')['ORDER_COUNT']
                        st.line_chart(chart_df, height=400)
                    else:
                        st.info("No medication data found in the last 5 years")
                else:
                    st.info("No medication data found for these codes - none have ever been ordered.")
            
            # Tab 2: Code Usage
            with tabs[1]:
                st.subheader("📋 Code Usage Analysis")
                
                # Always get cluster codes for analysis
                cluster_codes = cluster_member_codes()
                total_codes_in_cluster = len(cluster_codes) if not cluster_codes.empty else 0
                used_codes = len(med_df) if not med_df.empty else 0
                unused_codes = total_codes_in_cluster - used_codes
                
                # Code-level breakdown (only show if we have data)
                if not med_df.empty:
                    st.subheader("Medications Ever Ordered")
                    st.caption("Shows only medications that have been ordered at least once")
                    st.dataframe(
                        med_df[['CODE', 'DISPLAY', 'PERSON_COUNT', 'ORDER_COUNT']],
                        use_container_width=True
                    )
                    
                    # Download button
                    csv = med_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Medication Data",
                        data=csv,
                        file_name=f"{cluster_id}_medication_analytics.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No medication data found for these codes - none have ever been ordered.")
                
                # Show unused codes if any
                if unused_codes > 0:
                    st.subheader("Medications Never Ordered")
                    st.caption(f"These {unused_codes} medication(s) are in the cluster but have never been ordered")
                    
                    # Get unused codes
                    if not med_df.empty:
                        used_codes_set = set(med_df['CODE'].tolist())
                        all_codes_set = set(cluster_codes['CODE'].tolist()) if not cluster_codes.empty else set()
                        unused_codes_set = all_codes_set - used_codes_set
                        
                        if unused_codes_set:
                            unused_display_df = cluster_codes[cluster_codes['CODE'].isin(unused_codes_set)][['CODE', 'DISPLAY']]
                            st.dataframe(unused_display_df, use_container_width=True)
                    else:
                        # All codes are unused
                        st.dataframe(cluster_codes[['CODE', 'DISPLAY']], use_container_width=True)
            
            # Tab 3: Demographics
            with tabs[2]:
                st.subheader("👥 Age & Sex Distribution")
                st.markdown("Age and sex breakdown of patients with medication orders in this cluster")
                
                with st.spinner("Loading demographics data..."):
                    cluster_demographics = get_cluster_demographics(cluster_id, cluster_type, source=source)
                    
                    if not cluster_demographics.empty:
                        summary = cluster_demographics.iloc[0]
                        
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Active Patients", f"{summary['TOTAL_PATIENTS']:,.0f}")
                        with col2:
                            st.metric("Average Age", f"{summary['AVG_AGE']:.1f} years")
                        with col3:
                            male_pct = (summary['MALE_COUNT'] / summary['TOTAL_PATIENTS']) * 100
                            st.metric("Male %", f"{male_pct:.1f}%")
                        with col4:
                            female_pct = (summary['FEMALE_COUNT'] / summary['TOTAL_PATIENTS']) * 100
                            st.metric("Female %", f"{female_pct:.1f}%")
                        
                        # Population pyramid and age distribution charts
                        age_sex_dist = get_cluster_age_sex_distribution(cluster_id, cluster_type, source=source)
                        if not age_sex_dist.empty:
                            create_population_pyramid(age_sex_dist)
                            create_age_slope_chart(age_sex_dist)
                        else:
                            st.warning("No age/sex distribution data available")
                        
                        # Rates analysis moved to Care Teams tab
                    else:
                        st.info("No demographics data available for this cluster.")
            
            # Tab 4: Organisation Counts
            with tabs[3]:
                st.subheader("🏥 Organisation Analysis")
                st.markdown("Patient counts by organisational unit")
                
                with st.spinner("Loading organisation data..."):
                    # Load practice-level data (always needed for scatter plot)
                    practice_rates = get_cluster_standardized_rates(cluster_id, cluster_type, "Practice", source=source)
                    
                    if not practice_rates.empty:
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            total_patients = practice_rates['PATIENTS_WITH_CODE'].sum()
                            st.metric("Total Patients", f"{total_patients:,}")
                        with col2:
                            avg_rate = practice_rates['RATE_PER_1000'].mean()
                            st.metric("Average Rate", f"{avg_rate:.2f} per 1,000")
                        with col3:
                            new_patients = practice_rates['NEW_PATIENTS_30D'].sum()
                            st.metric("New (30 days)", f"{new_patients:,}")
                        with col4:
                            practice_count = len(practice_rates)
                            st.metric("Practices", practice_count)
                        
                        st.divider()
                        
                        # Always show practice scatter plot
                        st.subheader("Practice Distribution")
                        scatter_chart = create_practice_scatter(practice_rates)
                        if scatter_chart:
                            st.altair_chart(scatter_chart, use_container_width=True)
                        
                        # Aggregated view section
                        st.subheader("Aggregated View")
                        
                        # Aggregation level selector for bar chart
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            agg_level = st.selectbox(
                                "Aggregate by:",
                                options=["Borough", "PCN", "Neighbourhood"],
                                index=0,
                                help="Choose aggregation level for bar chart",
                                key="org_agg_level"
                            )
                        
                        # Load and display aggregated data
                        agg_rates = get_cluster_standardized_rates(cluster_id, cluster_type, agg_level, source=source)
                        if not agg_rates.empty:
                            bar_chart = create_org_bar_chart(agg_rates, agg_level)
                            if bar_chart:
                                st.altair_chart(bar_chart, use_container_width=True)
                        
                        # Data table (always visible)
                        st.subheader("Data Table")
                        
                        # Selector for which data to show in table
                        table_view = st.radio(
                            "Show data for:",
                            options=["Practices", agg_level],
                            horizontal=True,
                            key="table_view_selector"
                        )
                        
                        # Display appropriate data
                        if table_view == "Practices":
                            display_df = practice_rates.copy()
                        else:
                            display_df = agg_rates.copy()
                        
                        # Format the dataframe for display
                        display_df['RATE_PER_1000'] = display_df['RATE_PER_1000'].round(2)
                        display_df['AVG_AGE'] = display_df['AVG_AGE'].round(1)
                        
                        # Rename columns for display
                        display_df = display_df.rename(columns={
                            'UNIT_NAME': 'Practice' if table_view == "Practices" else agg_level,
                            'TOTAL_POPULATION': 'Population',
                            'PATIENTS_WITH_CODE': 'Patients',
                            'AVG_AGE': 'Avg Age',
                            'NEW_PATIENTS_30D': 'New (30d)',
                            'RATE_PER_1000': 'Rate/1000'
                        })
                        
                        st.dataframe(display_df, use_container_width=True)
                        
                        # Download button
                        csv = display_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Data",
                            data=csv,
                            file_name=f"rates_{table_view.lower().replace(' ', '_')}_{cluster_id}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No data available")
            
            # Tab 5: Health Equity
            with tabs[4]:
                st.subheader("⚖️ Health Equity Analysis")
                st.markdown("Analysis of health inequalities across different population groups")
                
                with st.spinner("Loading health equity data..."):
                    # Load all equity data
                    ethnicity_data = get_cluster_ethnicity_analysis(cluster_id, cluster_type, source=source)
                    deprivation_data = get_cluster_deprivation_analysis(cluster_id, cluster_type, source=source)
                    language_data = get_cluster_language_analysis(cluster_id, cluster_type, source=source)
                    neighbourhood_data = get_cluster_neighbourhood_analysis(cluster_id, cluster_type, source=source)
                    
                    # Ethnicity Analysis
                    st.subheader("📊 Ethnicity")
                    if not ethnicity_data.empty:
                        create_ethnicity_bar_chart(ethnicity_data)
                    else:
                        st.info("No ethnicity data available")
                    
                    st.divider()
                    
                    # Deprivation Analysis
                    st.subheader("💰 Social Deprivation")
                    if not deprivation_data.empty:
                        create_deprivation_bar_chart(deprivation_data)
                    else:
                        st.info("No deprivation data available")
                    
                    st.divider()
                    
                    # Language Analysis
                    st.subheader("🗣️ Language & Access")
                    if not language_data.empty:
                        create_language_bar_chart(language_data)
                    else:
                        st.info("No language data available")
                    
                    st.divider()
                    
                    # Neighbourhood Analysis
                    st.subheader("🏘️ Neighbourhood Comparison")
                    if not neighbourhood_data.empty:
                        create_neighbourhood_bar_chart(neighbourhood_data)
                    else:
                        st.info("No neighbourhood data available")
            
            # Tab 6: SQL Templates  
            with tabs[5]:
                st.subheader("SQL Query Templates")
                st.markdown("#### 💻 Data Export Queries")
                st.markdown("Copy these queries to extract data from Snowflake. Each query is ready to run - just paste into your SQL editor.")
                
                # Basic codes query
                st.markdown("### Get All Medication Codes in This Cluster")
                query1 = tmpl_codes_query
                st.code(query1, language='sql')
                
                # Patient medication list
                st.markdown("### Get Patients on These Medications")
                query2 = f"""-- Get list of patients with medication orders in cluster {cluster_id}
SELECT DISTINCT
    d.person_id,
    d.practice_name,
    d.age,
    d.gender,
    COUNT(DISTINCT mo.id) as order_count,
    MIN(mo.clinical_effective_date) as first_order,
    MAX(mo.clinical_effective_date) as last_order
FROM {tmpl_code_join}
JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
WHERE {tmpl_code_where}
AND d.is_active = true
GROUP BY d.person_id, d.practice_name, d.age, d.gender
ORDER BY order_count DESC;"""
                st.code(query2, language='sql')
                
                # Practice prescribing patterns
                st.markdown("### Prescribing Patterns by Practice")
                query3 = f"""-- Get practice-level prescribing for cluster {cluster_id}
SELECT 
    d.practice_name,
    d.pcn_name,
    d.borough_registered,
    COUNT(DISTINCT d.person_id) as patient_count,
    COUNT(DISTINCT mo.id) as total_orders,
    ROUND(AVG(d.age), 1) as avg_age,
    COUNT(DISTINCT CASE WHEN mo.clinical_effective_date >= DATEADD('day', -30, CURRENT_DATE()) THEN d.person_id END) as recent_patients_30d
FROM {tmpl_code_join}
JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
WHERE {tmpl_code_where}
AND d.is_active = true
GROUP BY d.practice_name, d.pcn_name, d.borough_registered
HAVING patient_count >= 5  -- Privacy threshold
ORDER BY patient_count DESC;"""
                st.code(query3, language='sql')
                
                # Monthly prescribing trends
                st.markdown("### Monthly Prescribing Trends")
                query4 = f"""-- Get monthly medication order counts for cluster {cluster_id}
SELECT 
    DATE_TRUNC('month', mo.clinical_effective_date) as month,
    COUNT(DISTINCT d.person_id) as unique_patients,
    COUNT(DISTINCT mo.id) as order_count,
    COUNT(DISTINCT ec.code) as unique_medications
FROM {tmpl_code_join}
JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
WHERE {tmpl_code_where}
AND mo.clinical_effective_date >= DATEADD('month', -24, CURRENT_DATE())
AND mo.clinical_effective_date < CURRENT_DATE()
GROUP BY DATE_TRUNC('month', mo.clinical_effective_date)
ORDER BY month DESC;"""
                st.code(query4, language='sql')
                
                # Top medications
                st.markdown("### Most Prescribed Medications")
                query5 = f"""-- Get top medications by patient count for cluster {cluster_id}
SELECT 
    ec.code,
    ec.display,
    COUNT(DISTINCT d.person_id) as patient_count,
    COUNT(DISTINCT mo.id) as total_orders,
    ROUND(COUNT(DISTINCT mo.id) * 1.0 / COUNT(DISTINCT d.person_id), 1) as avg_orders_per_patient
FROM {tmpl_code_join}
JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
WHERE {tmpl_code_where}
GROUP BY ec.code, ec.display
ORDER BY patient_count DESC
LIMIT 20;"""
                st.code(query5, language='sql')