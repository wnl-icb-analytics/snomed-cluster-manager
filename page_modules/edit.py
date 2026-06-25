# =============================================================================
# SNOMED Cluster Manager - Edit Existing Cluster Page
# =============================================================================

import streamlit as st
from database import rerun
from services.cluster_service import (
    get_all_clusters,
    get_cluster_versions,
    rename_cluster,
    restore_cluster_version,
    test_ecl_expression,
    update_existing_cluster,
)
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

    versions_df = get_cluster_versions(cluster_id)
    with st.expander(
        f"🕘 Definition History ({len(versions_df)} version(s))",
        expanded=False,
    ):
        if versions_df.empty:
            st.info("No saved definition versions are available.")
        else:
            version_options = versions_df['VERSION_ID'].tolist()

            def format_version(version_id):
                row = versions_df[versions_df['VERSION_ID'] == version_id].iloc[0]
                created_at = row.get('CREATED_AT')
                actor = row.get('CREATED_BY') or 'System'
                change_type = row.get('CHANGE_TYPE') or 'UPDATE'
                return (
                    f"v{int(row['VERSION_NUMBER'])} · {change_type} · "
                    f"{created_at} · {actor}"
                )

            selected_version_id = st.selectbox(
                "Select a saved version",
                options=version_options,
                format_func=format_version,
                key=f"restore_version_{cluster_id}",
            )
            selected_version = versions_df[
                versions_df['VERSION_ID'] == selected_version_id
            ].iloc[0]

            version_cols = st.columns(3)
            version_cols[0].metric(
                "Version", f"v{int(selected_version['VERSION_NUMBER'])}"
            )
            version_cols[1].metric(
                "Type", selected_version.get('CLUSTER_TYPE') or "—"
            )
            version_cols[2].metric(
                "Hash", str(selected_version.get('VERSION_HASH') or "")[:12]
            )

            if selected_version.get('DESCRIPTION'):
                st.markdown(f"*{selected_version.get('DESCRIPTION')}*")
            st.code(
                selected_version.get('ECL_EXPRESSION') or "",
                language='go',
            )
            st.caption(
                "Content hash: "
                f"`{selected_version.get('CONTENT_HASH')}`"
            )

            current_content = (
                cluster.get('ECL_EXPRESSION', ''),
                cluster.get('DESCRIPTION', ''),
                cluster.get('CLUSTER_TYPE', ''),
            )
            selected_content = (
                selected_version.get('ECL_EXPRESSION') or '',
                selected_version.get('DESCRIPTION') or '',
                selected_version.get('CLUSTER_TYPE') or '',
            )

            if selected_content == current_content:
                st.info("This version matches the current definition.")
            else:
                confirm_restore = st.checkbox(
                    "I understand this will replace the current definition and refresh its cache",
                    key=f"confirm_restore_{cluster_id}",
                )
                if st.button(
                    f"↩️ Restore v{int(selected_version['VERSION_NUMBER'])}",
                    type="secondary",
                    disabled=not confirm_restore,
                    key=f"restore_button_{cluster_id}",
                ):
                    with st.spinner("Restoring definition and refreshing cache..."):
                        restored, message = restore_cluster_version(
                            cluster_id,
                            selected_version_id,
                        )
                    if restored:
                        st.session_state["flash"] = (
                            "success",
                            f"✅ Restored {cluster_id} from "
                            f"v{int(selected_version['VERSION_NUMBER'])}.",
                        )
                        st.session_state.pop('edit_loaded_for', None)
                        rerun()
                    else:
                        st.error(f"❌ {message}")
    
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
                            st.session_state.selected_source = None  # authored
                            st.session_state.pop('edit_loaded_for', None)
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
                        st.session_state.selected_source = None  # authored
                        st.session_state.page = 'details'
                        rerun()
