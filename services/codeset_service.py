# =============================================================================
# SNOMED Cluster Manager - Codeset Service
# Unified access to authored ECL clusters and brought-in codesets
# (COMBINED_CODESETS: PCD, OpenCodelists, LTC_LCS, UKHSA, immunisations, etc.)
# =============================================================================

import pandas as pd
import streamlit as st
from database import get_connection
from config import APP_SCHEMA, AUTHORED_SOURCE, CODESETS_TABLE
from utils.codeset_sql import codeset_filter


conn = get_connection()

# Friendly labels for the brought-in sources that feed COMBINED_CODESETS
SOURCE_LABELS = {
    AUTHORED_SOURCE: 'Authored',
    'PCD': 'PCD / GDPPR',
    'OPENCODELISTS': 'OpenCodelists',
    'LTC_LCS': 'LTC LCS',
    'UKHSA_COVID': 'UKHSA COVID',
    'UKHSA_FLU': 'UKHSA Flu',
    'Q_ADMISSIONS': 'QAdmissions',
    'ADULT_IMMS': 'Adult Imms',
    'CHILDHOOD_IMMS': 'Childhood Imms',
}


def is_authored(source):
    """True when a codeset is authored in this app (not brought in)."""
    return source in (None, '', AUTHORED_SOURCE)


def source_label(source):
    """Human-friendly label for a codeset source."""
    return SOURCE_LABELS.get(source, source or 'Authored')


@st.cache_data(ttl=600, show_spinner=False)
def get_codeset_index():
    """Unified, searchable index of every codeset.

    Authored ECL clusters come from ECL_CLUSTERS (with metadata); brought-in
    codesets come from COMBINED_CODESETS keyed by (source, cluster_id).
    """
    try:
        query = f"""
        SELECT
            '{AUTHORED_SOURCE}' AS SOURCE,
            c.cluster_id AS CLUSTER_ID,
            c.description AS DESCRIPTION,
            c.cluster_type AS CLUSTER_TYPE,
            TRUE AS IS_AUTHORED,
            COALESCE(m.record_count, 0) AS CODE_COUNT,
            c.updated_at AS UPDATED_AT,
            c.updated_by AS UPDATED_BY
        FROM {APP_SCHEMA}.ECL_CLUSTERS c
        LEFT JOIN {APP_SCHEMA}.ECL_CACHE_METADATA m ON c.cluster_id = m.cluster_id
        UNION ALL
        SELECT
            source AS SOURCE,
            cluster_id AS CLUSTER_ID,
            MAX(cluster_description) AS DESCRIPTION,
            NULL AS CLUSTER_TYPE,
            FALSE AS IS_AUTHORED,
            COUNT(*) AS CODE_COUNT,
            NULL AS UPDATED_AT,
            NULL AS UPDATED_BY
        FROM {CODESETS_TABLE}
        WHERE source <> '{AUTHORED_SOURCE}'
        GROUP BY source, cluster_id
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading codeset index: {str(e)}")
        return pd.DataFrame()


def get_codeset_meta(cluster_id, source):
    """Single-row metadata for a brought-in codeset."""
    try:
        query = f"""
        SELECT
            source AS SOURCE,
            cluster_id AS CLUSTER_ID,
            MAX(cluster_description) AS DESCRIPTION,
            COUNT(*) AS CODE_COUNT
        FROM {CODESETS_TABLE}
        WHERE {codeset_filter(cluster_id, source)}
        GROUP BY source, cluster_id
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading codeset: {str(e)}")
        return pd.DataFrame()


def get_codeset_codes(cluster_id, source):
    """Published member codes for an authored or brought-in codeset."""
    try:
        query = f"""
        SELECT code AS CODE, code_description AS DISPLAY
        FROM {CODESETS_TABLE}
        WHERE {codeset_filter(cluster_id, source)}
        ORDER BY code
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading codeset codes: {str(e)}")
        return pd.DataFrame()
