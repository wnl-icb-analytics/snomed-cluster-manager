# =============================================================================
# SNOMED Cluster Manager - Cluster Service
# =============================================================================

import pandas as pd
import streamlit as st
from database import get_connection
from config import DB_SCHEMA, STALE_LABEL
from utils.helpers import normalize_whitespace


# Get connection instance
conn = get_connection()


def get_all_clusters():
    """Get all ECL clusters with metadata"""
    try:
        stale_label = STALE_LABEL
        query = f"""
        SELECT 
            c.cluster_id AS CLUSTER_ID,
            c.cluster_uid AS CLUSTER_UID,
            c.ecl_expression AS ECL_EXPRESSION,
            c.description AS DESCRIPTION,
            c.cluster_type AS CLUSTER_TYPE,
            c.created_at AS CREATED_AT,
            c.updated_at AS UPDATED_AT,
            c.created_by AS CREATED_BY,
            c.updated_by AS UPDATED_BY,
            m.last_successful_refresh AS LAST_SUCCESSFUL_REFRESH,
            m.last_attempted_refresh AS LAST_ATTEMPTED_REFRESH,
            m.last_refreshed_by AS LAST_REFRESHED_BY,
            m.last_attempted_by AS LAST_ATTEMPTED_BY,
            m.record_count AS RECORD_COUNT,
            m.last_error_message AS LAST_ERROR_MESSAGE,
            CASE 
                WHEN m.last_successful_refresh IS NULL THEN 'Never refreshed'
                WHEN m.last_successful_refresh < DATEADD(day, -28, CURRENT_TIMESTAMP()) THEN '{stale_label}'
                ELSE 'Fresh'
            END as STATUS,
            CASE 
                WHEN m.last_successful_refresh IS NULL THEN 'Never refreshed'
                WHEN m.last_successful_refresh < DATEADD(day, -28, CURRENT_TIMESTAMP()) THEN '{stale_label}'
                ELSE 'Fresh'
            END as STATUS_LABEL,
            m.last_successful_refresh AS LAST_UPDATED
        FROM {DB_SCHEMA}.ECL_CLUSTERS c
        LEFT JOIN {DB_SCHEMA}.ECL_CACHE_METADATA m ON c.cluster_id = m.cluster_id
        ORDER BY c.cluster_id
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error connecting to ECL tables: {str(e)}")
        st.info("Please ensure the ECL cache system is properly installed in DATA_LAKE__NCL.TERMINOLOGY schema.")
        return pd.DataFrame()


def test_ecl_expression(ecl_expr):
    """Test an ECL expression through the local 50k-limited wrapper."""
    try:
        safe_expr = ecl_expr.replace("'", "''")
        return conn.sql(
            f"""
            SELECT code, display, system
            FROM TABLE({DB_SCHEMA}.ECL_TEST_DETAILS('{safe_expr}'))
            """
        ).to_pandas()
    except Exception as e:
        st.error(f"ECL Error: {str(e)}")
        return pd.DataFrame()


def get_cluster_cache(cluster_id):
    """Get cached codes for a cluster - only latest refresh"""
    try:
        normalized_cluster_id_upper = cluster_id.upper().strip()
        
        # Get the latest refresh timestamp for this cluster
        latest_refresh_query = f"""
        SELECT MAX(last_refreshed) as latest_refresh
        FROM {DB_SCHEMA}.ECL_CACHE
        WHERE UPPER(cluster_id) = '{normalized_cluster_id_upper}'
        """
        latest_result = conn.sql(latest_refresh_query).to_pandas()
        
        if latest_result.empty or latest_result.iloc[0, 0] is None:
            return pd.DataFrame()
            
        latest_refresh = latest_result.iloc[0, 0]
        
        # Get only codes from the latest refresh
        query = f"""
        SELECT code, display, system, last_refreshed
        FROM {DB_SCHEMA}.ECL_CACHE
        WHERE UPPER(cluster_id) = '{normalized_cluster_id_upper}'
        AND last_refreshed = '{latest_refresh}'
        ORDER BY code
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Cache Error: {str(e)}")
        return pd.DataFrame()


def refresh_cluster(cluster_id, force=False):
    """Refresh a specific cluster"""
    try:
        normalized_cluster_id = cluster_id.strip()
        safe_cluster_id = normalized_cluster_id.replace("'", "''")
        
        if force:
            query = f"CALL {DB_SCHEMA}.FORCE_REFRESH_ECL_CLUSTER('{safe_cluster_id}')"
        else:
            query = f"CALL {DB_SCHEMA}.REFRESH_ECL_CLUSTER('{safe_cluster_id}')"
        
        result = conn.sql(query).to_pandas()
        return result.iloc[0, 0] if not result.empty else "No result"
    except Exception as e:
        return f"Error: {str(e)}"


def refresh_all_clusters(force=False):
    """Refresh all clusters using the bulk procedure when available."""
    actor = st.user.get("email") if hasattr(st, "user") else None
    actor_safe = ((actor or "").upper()).replace("'", "''")
    force_sql = "TRUE" if force else "FALSE"

    try:
        query = f"CALL {DB_SCHEMA}.REFRESH_ALL_ECL_CLUSTERS({force_sql}, '{actor_safe}')"
        result = conn.sql(query).to_pandas()
        return result.iloc[0, 0] if not result.empty else "No result"
    except Exception:
        try:
            query = f"CALL {DB_SCHEMA}.REFRESH_ALL_ECL_CLUSTERS({force_sql})"
            result = conn.sql(query).to_pandas()
            return result.iloc[0, 0] if not result.empty else "No result"
        except Exception as e:
            return f"Error: {str(e)}"


def get_cluster_change_history(cluster_id, limit=50):
    """Get change history for a cluster from ECL_CLUSTER_CHANGES table"""
    try:
        safe_cluster_id = cluster_id.strip().replace("'", "''")
        query = f"""
        SELECT 
            change_id,
            change_type,
            code,
            display,
            system,
            change_timestamp,
            changed_by,
            refresh_session_id
        FROM {DB_SCHEMA}.ECL_CLUSTER_CHANGES
        WHERE cluster_id = '{safe_cluster_id}'
        ORDER BY change_timestamp DESC
        LIMIT {limit}
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Change History Error: {str(e)}")
        return pd.DataFrame()


def get_cluster_change_summary(cluster_id, days=30):
    """Get summary of changes over time for a cluster"""
    try:
        safe_cluster_id = cluster_id.strip().replace("'", "''")
        query = f"""
        SELECT 
            DATE(change_timestamp) as change_date,
            change_type,
            COUNT(*) as change_count,
            refresh_session_id
        FROM {DB_SCHEMA}.ECL_CLUSTER_CHANGES
        WHERE cluster_id = '{safe_cluster_id}'
        AND change_timestamp >= DATEADD(day, -{days}, CURRENT_TIMESTAMP())
        GROUP BY DATE(change_timestamp), change_type, refresh_session_id
        ORDER BY change_date DESC, change_type
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Change Summary Error: {str(e)}")
        return pd.DataFrame()


def get_recent_cluster_changes(limit=100):
    """Get recent changes across all clusters"""
    try:
        query = f"""
        SELECT 
            c.cluster_id,
            c.change_type,
            c.code,
            c.display,
            c.change_timestamp,
            c.changed_by,
            c.refresh_session_id
        FROM {DB_SCHEMA}.ECL_CLUSTER_CHANGES c
        ORDER BY c.change_timestamp DESC
        LIMIT {limit}
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Recent Changes Error: {str(e)}")
        return pd.DataFrame()


def get_cluster_versions(cluster_id, limit=100):
    """Get append-only definition versions for an authored cluster."""
    try:
        safe_id = cluster_id.upper().strip().replace("'", "''")
        safe_limit = max(1, min(int(limit), 500))
        query = f"""
        SELECT
            v.version_id AS VERSION_ID,
            v.version_hash AS VERSION_HASH,
            v.content_hash AS CONTENT_HASH,
            v.ecl_expression_hash AS ECL_EXPRESSION_HASH,
            v.version_number AS VERSION_NUMBER,
            v.cluster_id AS CLUSTER_ID_AT_VERSION,
            v.ecl_expression AS ECL_EXPRESSION,
            v.description AS DESCRIPTION,
            v.cluster_type AS CLUSTER_TYPE,
            v.change_type AS CHANGE_TYPE,
            v.source_version_id AS SOURCE_VERSION_ID,
            v.created_at AS CREATED_AT,
            v.created_by AS CREATED_BY,
            v.comment AS COMMENT
        FROM {DB_SCHEMA}.ECL_CLUSTER_VERSIONS v
        JOIN {DB_SCHEMA}.ECL_CLUSTERS c
          ON c.cluster_uid = v.cluster_uid
        WHERE c.cluster_id = '{safe_id}'
        ORDER BY v.version_number DESC
        LIMIT {safe_limit}
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Version History Error: {str(e)}")
        return pd.DataFrame()


def restore_cluster_version(cluster_id, version_id):
    """Restore an authored cluster definition from an append-only version."""
    try:
        safe_id = cluster_id.upper().strip().replace("'", "''")
        safe_version_id = str(version_id).strip().replace("'", "''")
        actor = st.user.get("email") if hasattr(st, "user") else None
        actor_safe = ((actor or "").upper()).replace("'", "''")
        query = (
            f"CALL {DB_SCHEMA}.RESTORE_ECL_CLUSTER_VERSION("
            f"'{safe_id}', '{safe_version_id}', '{actor_safe}')"
        )
        result = conn.sql(query).to_pandas()
        message = str(result.iloc[0, 0]) if not result.empty else "No result"
        if message.startswith("SUCCESS"):
            return True, message
        return False, message
    except Exception as e:
        return False, f"Restore failed: {str(e)}"


def cluster_matches_expected(cluster_id: str, expected_ecl: str, expected_desc: str) -> bool:
    """Check if cluster matches expected values"""
    try:
        safe_id = cluster_id.upper().strip().replace("'", "''")
        df = conn.sql(
            f"""
            SELECT ecl_expression, description
            FROM {DB_SCHEMA}.ECL_CLUSTERS
            WHERE cluster_id = '{safe_id}'
            """
        ).to_pandas()
        if df.empty:
            return False
        current_ecl = normalize_whitespace(df.iloc[0]["ECL_EXPRESSION"]) if "ECL_EXPRESSION" in df.columns else ""
        current_desc = normalize_whitespace(df.iloc[0]["DESCRIPTION"]) if "DESCRIPTION" in df.columns else ""
        return current_ecl == normalize_whitespace(expected_ecl) and current_desc == normalize_whitespace(expected_desc)
    except Exception:
        return False


def create_new_cluster(cluster_id, ecl_expression, description, cluster_type='OBSERVATION'):
    """Create a new cluster - prevents duplicates"""
    try:
        safe_id = cluster_id.upper().strip().replace("'", "''")
        safe_ecl = ecl_expression.replace("'", "''").replace("\n", " ").replace("\r", " ")
        safe_desc = description.replace("'", "''").replace("\n", " ").replace("\r", " ")
        safe_type = cluster_type.upper() if cluster_type else 'OBSERVATION'
        actor = st.user.get("email") if hasattr(st, 'user') else None
        actor_upper = (actor or "").upper()
        actor_safe = actor_upper.replace("'", "''")

        existing = conn.sql(
            f"""
            SELECT COUNT(*) AS cluster_count
            FROM {DB_SCHEMA}.ECL_CLUSTERS
            WHERE cluster_id = '{safe_id}'
            """
        ).to_pandas()
        if not existing.empty and int(existing.iloc[0]['CLUSTER_COUNT']) > 0:
            st.error(f"❌ Cluster '{safe_id}' already exists")
            return False

        query = f"CALL {DB_SCHEMA}.UPSERT_ECL_CLUSTER('{safe_id}', '{safe_ecl}', '{safe_desc}', '{actor_safe}', '{safe_type}')"
        result = conn.sql(query).to_pandas()
        if result.empty:
            if cluster_matches_expected(safe_id, ecl_expression, description):
                return True
            st.error("❌ Procedure returned no result")
            return False
        msg = str(result.iloc[0, 0])
        if msg.startswith("SUCCESS"):
            return True
        else:
            if cluster_matches_expected(safe_id, ecl_expression, description):
                return True
            st.error(f"❌ {msg}")
            return False
    except Exception as e:
        if cluster_matches_expected(safe_id, ecl_expression, description):
            return True
        
        details = getattr(e, 'msg', None) or str(e)
        sfqid = getattr(e, 'sfqid', None)
        errno = getattr(e, 'errno', None)
        sqlstate = getattr(e, 'sqlstate', None)
        meta = f" [errno={errno}, sqlstate={sqlstate}, sfqid={sfqid}]" if (errno or sqlstate or sfqid) else ""
        st.error(f"❌ Failed to create cluster: {details}{meta}")
        return False


def update_existing_cluster(cluster_id, ecl_expression, description, cluster_type='OBSERVATION'):
    """Update an existing cluster"""
    try:
        safe_id = cluster_id.upper().strip().replace("'", "''")
        safe_ecl = ecl_expression.replace("'", "''").replace("\n", " ").replace("\r", " ")
        safe_desc = description.replace("'", "''").replace("\n", " ").replace("\r", " ")
        safe_type = cluster_type.upper() if cluster_type else 'OBSERVATION'
        actor = st.user.get("email") if hasattr(st, 'user') else None
        actor_upper = (actor or "").upper()
        actor_safe = actor_upper.replace("'", "''")
        query = f"CALL {DB_SCHEMA}.UPSERT_ECL_CLUSTER('{safe_id}', '{safe_ecl}', '{safe_desc}', '{actor_safe}', '{safe_type}')"
        result = conn.sql(query).to_pandas()
        if result.empty:
            if cluster_matches_expected(safe_id, ecl_expression, description):
                return True
            st.error("❌ Update failed: procedure returned no result")
            return False
        msg = str(result.iloc[0, 0])
        if msg.startswith("SUCCESS"):
            return True
        else:
            if cluster_matches_expected(safe_id, ecl_expression, description):
                return True
            st.error(f"Update Error: {msg}")
            return False
    except Exception as e:
        if cluster_matches_expected(safe_id, ecl_expression, description):
            return True

        details = getattr(e, 'msg', None) or str(e)
        sfqid = getattr(e, 'sfqid', None)
        errno = getattr(e, 'errno', None)
        sqlstate = getattr(e, 'sqlstate', None)
        meta = f" [errno={errno}, sqlstate={sqlstate}, sfqid={sfqid}]" if (errno or sqlstate or sfqid) else ""
        st.error(f"Update Error: {details}{meta}")
        return False


def delete_cluster(cluster_id):
    """Delete a cluster and its cache"""
    try:
        safe_id = cluster_id.strip().replace("'", "''")
        result = conn.sql(f"CALL {DB_SCHEMA}.DELETE_ECL_CLUSTER('{safe_id}')").collect()
        
        # Check if the stored procedure returned an error
        if result and len(result) > 0:
            result_msg = result[0][0]  # Get the return message from the procedure
            if result_msg.startswith('ERROR'):
                st.session_state["delete_error"] = f"Delete failed: {result_msg}"
                st.error(f"Delete procedure returned: {result_msg}")
                return False
            else:
                st.success(f"Delete procedure returned: {result_msg}")
                return True
        else:
            st.warning("Delete procedure returned no result")
            return True
    except Exception as e:
        error_msg = f"Delete failed: {str(e)}"
        st.session_state["delete_error"] = error_msg
        st.error(error_msg)
        return False


def rename_cluster(old_cluster_id: str, new_cluster_id: str, ecl_expression: str, description: str, cluster_type: str = None) -> bool:
    """Rename a cluster across all tables in a single transaction"""
    try:
        safe_old = old_cluster_id.strip().replace("'", "''")
        safe_new = new_cluster_id.upper().strip().replace("'", "''")
        safe_ecl = ecl_expression.replace("'", "''").replace("\n", " ").replace("\r", " ")
        safe_desc = description.replace("'", "''").replace("\n", " ").replace("\r", " ")
        actor = st.user.get("email") if hasattr(st, 'user') else None
        actor_upper = (actor or "").upper()
        actor_safe = actor_upper.replace("'", "''")
        safe_type = cluster_type.upper() if cluster_type else 'NULL'
        
        if safe_type == 'NULL':
            query = f"CALL {DB_SCHEMA}.RENAME_ECL_CLUSTER('{safe_old}', '{safe_new}', '{safe_ecl}', '{safe_desc}', '{actor_safe}', NULL)"
        else:
            query = f"CALL {DB_SCHEMA}.RENAME_ECL_CLUSTER('{safe_old}', '{safe_new}', '{safe_ecl}', '{safe_desc}', '{actor_safe}', '{safe_type}')"
        result = conn.sql(query).to_pandas()
        if result.empty:
            st.error("❌ Rename failed: procedure returned no result")
            return False
        msg = str(result.iloc[0, 0])
        if msg.startswith("SUCCESS"):
            return True
        else:
            st.error(f"❌ {msg}")
            return False
    except Exception as e:
        details = getattr(e, 'msg', None) or str(e)
        sfqid = getattr(e, 'sfqid', None)
        errno = getattr(e, 'errno', None)
        sqlstate = getattr(e, 'sqlstate', None)
        meta = f" [errno={errno}, sqlstate={sqlstate}, sfqid={sfqid}]" if (errno or sqlstate or sfqid) else ""
        st.error(f"❌ Rename error: {details}{meta}")
        return False
