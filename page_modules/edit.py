# =============================================================================
# SNOMED Cluster Manager - Edit Existing Cluster Page
# =============================================================================

import streamlit as st
from database import rerun
from services.cluster_service import test_ecl_expression, update_existing_cluster, rename_cluster, get_all_clusters
from components.cluster_components import render_flash_message


def render_edit():
    """Render the Edit Existing Cluster page"""
    if not st.session_state.selected_cluster:
        st.error("No cluster selected")
        st.session_state.page = 'home'
        rerun()
    
    cluster_id = st.session_state.selected_cluster
    
    # Get cluster info
    clusters_df = get_all_clusters()
    cluster_info = clusters_df[clusters_df['CLUSTER_ID'] == cluster_id]
    if cluster_info.empty:
        st.error(f"Cluster '{cluster_id}' not found")
        st.session_state.page = 'home'
        rerun()
    
    cluster = cluster_info.iloc[0]

    # Keep the ECL editor in sync with the selected cluster. A widget `value=` is
    # ignored once its key exists in session state, so set the key explicitly when
    # the selected cluster changes - otherwise editing B after A shows A's ECL.
    if st.session_state.get("edit_loaded_for") != cluster_id:
        st.session_state["edit_ecl_input"] = cluster.get("ECL_EXPRESSION", "")
        st.session_state["edit_loaded_for"] = cluster_id

    # Header
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = 'details'
            rerun()
    with col2:
        st.title(f"✏️ Edit: {cluster_id}")
    
    # Flash message component
    render_flash_message()
    
    # Rename cluster section
    with st.expander("🏷️ Rename Cluster", expanded=False):
        st.warning("⚠️ **Caution**: Renaming affects all cached data and history. Use carefully.")
        
        new_cluster_id = st.text_input(
            "New Cluster ID",
            value=cluster_id,
            help="Enter new cluster ID (will be converted to uppercase)"
        ).strip().upper()
        
        if new_cluster_id and new_cluster_id != cluster_id:
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 Rename", type="secondary", use_container_width=True):
                    with st.spinner("Renaming cluster..."):
                        if rename_cluster(cluster_id, new_cluster_id, cluster['ECL_EXPRESSION'], cluster['DESCRIPTION'], cluster.get('CLUSTER_TYPE')):
                            st.session_state["flash"] = ("success", f"✅ Cluster renamed from '{cluster_id}' to '{new_cluster_id}'!")
                            st.session_state.selected_cluster = new_cluster_id
                            rerun()
    
    # Edit form
    with st.form("edit_cluster_form"):
        st.subheader("📝 Edit Cluster Details")
        
        description = st.text_input(
            "Description *",
            value=cluster.get('DESCRIPTION', ''),
            placeholder="Brief description of what this cluster contains"
        )
        
        current_type = cluster.get('CLUSTER_TYPE', 'OBSERVATION')
        cluster_type = st.selectbox(
            "Cluster Type",
            options=['OBSERVATION', 'MEDICATION'],
            index=['OBSERVATION', 'MEDICATION'].index(current_type) if current_type in ['OBSERVATION', 'MEDICATION'] else 0,
            help="Type of clinical data this cluster represents"
        )
        
        ecl_expression = st.text_area(
            "ECL Expression *",
            height=150,
            placeholder="Enter SNOMED CT ECL expression",
            help="Expression Constraint Language query to define cluster contents",
            key="edit_ecl_input"
        )
        
        # Submit button
        col1, col2 = st.columns([3, 1])
        with col2:
            submit_clicked = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
        
        if submit_clicked:
            # Validation
            errors = []
            if not description:
                errors.append("Description is required")
            if not ecl_expression.strip():
                errors.append("ECL Expression is required")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Get the most current ECL value from widget
                current_ecl = st.session_state.get("edit_ecl_input", ecl_expression).strip()
                
                # Test ECL expression if changed
                if current_ecl != cluster.get('ECL_EXPRESSION', ''):
                    st.info("🧪 Testing updated ECL expression...")
                    test_result = test_ecl_expression(current_ecl)
                    
                    if test_result.empty:
                        st.error("❌ ECL expression is invalid or returns no results. Please test in the Playground first.")
                        st.stop()
                    else:
                        st.success(f"✅ ECL expression is valid! Found {len(test_result):,} codes")
                
                # Update cluster
                with st.spinner("Updating cluster..."):
                    if update_existing_cluster(cluster_id, current_ecl, description, cluster_type):
                        st.session_state["flash"] = ("success", f"✅ Cluster '{cluster_id}' updated successfully!")
                        st.session_state.page = 'details'
                        rerun()