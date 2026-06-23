# =============================================================================
# SNOMED Cluster Manager - Analytics Service
# =============================================================================

import pandas as pd
import streamlit as st
from database import get_connection
from config import DB_SCHEMA, DB_ANALYTICS, DB_STORE, DB_DEMOGRAPHICS


# Get connection instance
conn = get_connection()


def _code_source(source=None):
    """Code-membership source for a codeset.

    Authored clusters read live ecl_cache; brought-in codesets read
    COMBINED_CODESETS filtered by source. The returned subquery exposes
    (code, cluster_id) so existing `ec.cluster_id = '...'` filters work for both.
    """
    if source and source != 'ECL_CACHE':
        safe_src = str(source).replace("'", "''")
        return (f"(SELECT code, code_description AS display, cluster_id "
                f"FROM {DB_SCHEMA}.COMBINED_CODESETS WHERE source = '{safe_src}')")
    return f"{DB_SCHEMA}.ecl_cache"


def get_observation_analytics(cluster_id, source=None):
    """Get observation analytics for cluster codes"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            ec.code,
            ec.display,
            COUNT(DISTINCT d.person_id) as person_count,
            COUNT(DISTINCT o.id) as observation_count
        FROM {DB_STORE}.observation o
        JOIN {code_src} ec ON o.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        GROUP BY ec.code, ec.display
        ORDER BY person_count DESC
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading observation data: {str(e)}")
        return pd.DataFrame()


def get_medication_analytics(cluster_id, source=None):
    """Get medication analytics for cluster codes"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            ec.code,
            ec.display,
            COUNT(DISTINCT d.person_id) as person_count,
            COUNT(DISTINCT mo.id) as order_count
        FROM {DB_STORE}.medication_order mo
        JOIN {code_src} ec ON mo.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        GROUP BY ec.code, ec.display
        ORDER BY person_count DESC
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading medication data: {str(e)}")
        return pd.DataFrame()


def get_distinct_persons_med(cluster_id, source=None):
    """Get distinct person counts for medications"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            COUNT(DISTINCT d.person_id) as total_persons,
            COUNT(DISTINCT CASE WHEN d.is_active THEN d.person_id END) as active_persons,
            COUNT(DISTINCT mo.id) as total_orders
        FROM {DB_STORE}.medication_order mo
        JOIN {code_src} ec ON mo.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        """
        result = conn.sql(query).to_pandas()
        if not result.empty:
            return (result.iloc[0]['TOTAL_PERSONS'] or 0, 
                   result.iloc[0]['ACTIVE_PERSONS'] or 0,
                   result.iloc[0]['TOTAL_ORDERS'] or 0)
        return 0, 0, 0
    except Exception as e:
        st.error(f"Error loading distinct persons: {str(e)}")
        return 0, 0, 0


def get_medication_time_series(cluster_id, source=None):
    """Get medication time series data"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            DATE_TRUNC('month', mo.clinical_effective_date) as month_year,
            COUNT(DISTINCT mo.id) as order_count
        FROM {DB_STORE}.medication_order mo
        JOIN {code_src} ec ON mo.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        AND mo.clinical_effective_date >= DATE_TRUNC('month', DATEADD(month, -60, CURRENT_DATE()))
        AND mo.clinical_effective_date < DATE_TRUNC('month', CURRENT_DATE())
        AND mo.clinical_effective_date IS NOT NULL
        GROUP BY DATE_TRUNC('month', mo.clinical_effective_date)
        ORDER BY month_year
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading time series data: {str(e)}")
        return pd.DataFrame()


def get_distinct_persons_obs(cluster_id, source=None):
    """Get distinct person counts for observations"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            COUNT(DISTINCT d.person_id) as total_persons,
            COUNT(DISTINCT CASE WHEN d.is_active THEN d.person_id END) as active_persons,
            COUNT(DISTINCT o.id) as total_observations
        FROM {DB_STORE}.observation o
        JOIN {code_src} ec ON o.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        """
        result = conn.sql(query).to_pandas()
        if not result.empty:
            return (result.iloc[0]['TOTAL_PERSONS'] or 0, 
                   result.iloc[0]['ACTIVE_PERSONS'] or 0,
                   result.iloc[0]['TOTAL_OBSERVATIONS'] or 0)
        return 0, 0, 0
    except Exception as e:
        st.error(f"Error loading distinct persons: {str(e)}")
        return 0, 0, 0


def get_observation_time_series(cluster_id, source=None):
    """Get observation time series data"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            DATE_TRUNC('month', o.clinical_effective_date) as month_year,
            COUNT(DISTINCT o.id) as observation_count
        FROM {DB_STORE}.observation o
        JOIN {code_src} ec ON o.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        AND o.clinical_effective_date >= DATE_TRUNC('month', DATEADD(month, -60, CURRENT_DATE()))
        AND o.clinical_effective_date < DATE_TRUNC('month', CURRENT_DATE())
        AND o.clinical_effective_date IS NOT NULL
        GROUP BY DATE_TRUNC('month', o.clinical_effective_date)
        ORDER BY month_year
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading time series data: {str(e)}")
        return pd.DataFrame()


def get_medication_time_series(cluster_id, source=None):
    """Get medication time series data"""
    try:
        code_src = _code_source(source)
        query = f"""
        SELECT 
            DATE_TRUNC('month', mo.clinical_effective_date) as month_year,
            COUNT(DISTINCT mo.id) as order_count
        FROM {DB_STORE}.medication_order mo
        JOIN {code_src} ec ON mo.mapped_concept_code = ec.code
        JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
        WHERE ec.cluster_id = '{cluster_id}'
        AND mo.clinical_effective_date >= DATE_TRUNC('month', DATEADD(month, -60, CURRENT_DATE()))
        AND mo.clinical_effective_date < DATE_TRUNC('month', CURRENT_DATE())
        AND mo.clinical_effective_date IS NOT NULL
        GROUP BY DATE_TRUNC('month', mo.clinical_effective_date)
        ORDER BY month_year
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading time series data: {str(e)}")
        return pd.DataFrame()


def get_cluster_demographics(cluster_id, cluster_type, source=None):
    """Get demographic summary for patients with codes in a specific cluster"""
    try:
        code_src = _code_source(source)
        
        # Choose the right table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            SELECT 
                COUNT(DISTINCT CASE WHEN d.is_active = true THEN d.person_id END) as total_patients,
                AVG(CASE WHEN d.is_active = true THEN d.age END) as avg_age,
                COUNT(DISTINCT CASE WHEN d.is_active = true AND d.gender = 'Male' THEN d.person_id END) as male_count,
                COUNT(DISTINCT CASE WHEN d.is_active = true AND d.gender = 'Female' THEN d.person_id END) as female_count
            FROM {DB_STORE}.observation o
            JOIN {code_src} ec ON o.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            """
        else:  # MEDICATION
            query = f"""
            SELECT 
                COUNT(DISTINCT CASE WHEN d.is_active = true THEN d.person_id END) as total_patients,
                AVG(CASE WHEN d.is_active = true THEN d.age END) as avg_age,
                COUNT(DISTINCT CASE WHEN d.is_active = true AND d.gender = 'Male' THEN d.person_id END) as male_count,
                COUNT(DISTINCT CASE WHEN d.is_active = true AND d.gender = 'Female' THEN d.person_id END) as female_count
            FROM {DB_STORE}.medication_order m
            JOIN {code_src} ec ON m.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON m.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading cluster demographics: {str(e)}")
        return pd.DataFrame()


def get_cluster_age_sex_distribution(cluster_id, cluster_type, source=None):
    """Get age/sex distribution for patients with codes in a specific cluster"""
    try:
        code_src = _code_source(source)
        # Choose the right table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            SELECT 
                d.age_band_5y AS AGE_BAND,
                d.gender AS SEX,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT
            FROM {DB_STORE}.observation o
            JOIN {code_src} ec ON o.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.gender IN ('Male', 'Female')
            GROUP BY d.age_band_5y, d.gender
            ORDER BY d.age_band_5y, d.gender
            """
        else:  # MEDICATION
            query = f"""
            SELECT 
                d.age_band_5y AS AGE_BAND,
                d.gender AS SEX,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT
            FROM {DB_STORE}.medication_order m
            JOIN {code_src} ec ON m.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON m.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.gender IN ('Male', 'Female')
            GROUP BY d.age_band_5y, d.gender
            ORDER BY d.age_band_5y, d.gender
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading cluster age/sex distribution: {str(e)}")
        return pd.DataFrame()


def get_cluster_care_team_analysis(cluster_id, cluster_type, source=None):
    """Get care team analysis for patients with codes in a specific cluster"""
    try:
        code_src = _code_source(source)
        
        # Choose the right table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            SELECT 
                d.practice_name as practice_name,
                d.pcn_name as pcn_name,
                COUNT(DISTINCT d.person_id) as total_patients,
                AVG(d.age) as avg_age,
                COUNT(DISTINCT CASE WHEN d.gender = 'Male' THEN d.person_id END) as male_count,
                COUNT(DISTINCT CASE WHEN d.gender = 'Female' THEN d.person_id END) as female_count,
                COUNT(DISTINCT CASE WHEN d.age < 15 THEN d.person_id END) as children_count,
                COUNT(DISTINCT CASE WHEN d.age >= 65 THEN d.person_id END) as elderly_count
            FROM {DB_STORE}.observation o
            JOIN {code_src} ec ON o.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            GROUP BY d.practice_name, d.pcn_name
            HAVING COUNT(DISTINCT d.person_id) >= 5  -- Privacy threshold
            ORDER BY total_patients DESC
            """
        else:  # MEDICATION
            query = f"""
            SELECT 
                d.practice_name as practice_name,
                d.pcn_name as pcn_name,
                COUNT(DISTINCT d.person_id) as total_patients,
                AVG(d.age) as avg_age,
                COUNT(DISTINCT CASE WHEN d.gender = 'Male' THEN d.person_id END) as male_count,
                COUNT(DISTINCT CASE WHEN d.gender = 'Female' THEN d.person_id END) as female_count,
                COUNT(DISTINCT CASE WHEN d.age < 15 THEN d.person_id END) as children_count,
                COUNT(DISTINCT CASE WHEN d.age >= 65 THEN d.person_id END) as elderly_count
            FROM {DB_STORE}.medication_order m
            JOIN {code_src} ec ON m.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON m.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            GROUP BY d.practice_name, d.pcn_name
            HAVING COUNT(DISTINCT d.person_id) >= 5  -- Privacy threshold
            ORDER BY total_patients DESC
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading cluster care team analysis: {str(e)}")
        return pd.DataFrame()


def get_cluster_standardized_rates(cluster_id, cluster_type, agg_level="Borough", source=None):
    """Get simple rates table by organisational level"""
    try:
        code_src = _code_source(source)
        # Choose aggregation column
        if agg_level == "Practice":
            group_col = "PRACTICE_NAME"
            group_label = "Practice"
        elif agg_level == "PCN":
            group_col = "PCN_NAME"
            group_label = "PCN"
        elif agg_level == "Borough":
            group_col = "BOROUGH_REGISTERED"
            group_label = "Borough"
        else:  # Neighbourhood
            group_col = "NEIGHBOURHOOD_REGISTERED"
            group_label = "Neighbourhood"
        
        # Get date column name and join logic based on cluster type
        if cluster_type == 'OBSERVATION':
            date_col = "CLINICAL_EFFECTIVE_DATE"  # observation event date
            # Optimized query for observations - start from cluster codes
            query = f"""
            WITH cluster_patients AS (
                -- First get all patients with the cluster codes
                SELECT DISTINCT 
                    d.person_id,
                    d.{group_col},
                    d.age,
                    MIN(o.{date_col}) AS first_code_date,
                    MAX(o.{date_col}) AS last_code_date
                FROM {code_src} ec
                JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
                JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
                WHERE ec.cluster_id = '{cluster_id}'
                AND d.is_active = true
                AND d.{group_col} IS NOT NULL
                GROUP BY d.person_id, d.{group_col}, d.age
            ),
            total_pop AS (
                -- Get total population per unit for rate calculation
                SELECT 
                    {group_col},
                    COUNT(DISTINCT person_id) AS total_population,
                    AVG(age) AS avg_age_all
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
                WHERE is_active = true
                AND {group_col} IS NOT NULL
                GROUP BY {group_col}
            )
            SELECT 
                tp.{group_col} AS UNIT_NAME,
                tp.total_population,
                COUNT(DISTINCT cp.person_id) AS patients_with_code,
                ROUND(AVG(cp.age), 1) AS avg_age,
                COUNT(DISTINCT CASE 
                    WHEN cp.last_code_date >= DATEADD('day', -30, CURRENT_DATE())
                    THEN cp.person_id 
                END) AS new_patients_30d,
                ROUND(
                    COUNT(DISTINCT cp.person_id) * 1000.0 / tp.total_population, 
                    2
                ) AS rate_per_1000
            FROM total_pop tp
            LEFT JOIN cluster_patients cp ON tp.{group_col} = cp.{group_col}
            WHERE tp.total_population >= 100  -- Minimum population
            GROUP BY tp.{group_col}, tp.total_population
            ORDER BY rate_per_1000 DESC
            """
        else:  # MEDICATION
            date_col = "CLINICAL_EFFECTIVE_DATE"
            # Optimized query for medications - start from cluster codes
            query = f"""
            WITH cluster_patients AS (
                -- First get all patients with the cluster codes
                SELECT DISTINCT 
                    d.person_id,
                    d.{group_col},
                    d.age,
                    MIN(mo.{date_col}) AS first_code_date,
                    MAX(mo.{date_col}) AS last_code_date
                FROM {code_src} ec
                JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
                JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
                WHERE ec.cluster_id = '{cluster_id}'
                AND d.is_active = true
                AND d.{group_col} IS NOT NULL
                GROUP BY d.person_id, d.{group_col}, d.age
            ),
            total_pop AS (
                -- Get total population per unit for rate calculation
                SELECT 
                    {group_col},
                    COUNT(DISTINCT person_id) AS total_population,
                    AVG(age) AS avg_age_all
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
                WHERE is_active = true
                AND {group_col} IS NOT NULL
                GROUP BY {group_col}
            )
            SELECT 
                tp.{group_col} AS UNIT_NAME,
                tp.total_population,
                COUNT(DISTINCT cp.person_id) AS patients_with_code,
                ROUND(AVG(cp.age), 1) AS avg_age,
                COUNT(DISTINCT CASE 
                    WHEN cp.last_code_date >= DATEADD('day', -30, CURRENT_DATE())
                    THEN cp.person_id 
                END) AS new_patients_30d,
                ROUND(
                    COUNT(DISTINCT cp.person_id) * 1000.0 / tp.total_population, 
                    2
                ) AS rate_per_1000
            FROM total_pop tp
            LEFT JOIN cluster_patients cp ON tp.{group_col} = cp.{group_col}
            WHERE tp.total_population >= 100  -- Minimum population
            GROUP BY tp.{group_col}, tp.total_population
            ORDER BY rate_per_1000 DESC
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading rates: {str(e)}")
        return pd.DataFrame()


def get_cluster_ethnicity_analysis(cluster_id, cluster_type, source=None):
    """Get ethnicity breakdown for patients with codes in cluster"""
    try:
        code_src = _code_source(source)
        # Choose table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND ethnicity_subcategory IS NOT NULL
            )
            SELECT 
                d.ethnicity_subcategory AS ETHNICITY,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.ethnicity_subcategory IS NOT NULL
            GROUP BY d.ethnicity_subcategory, tp.total_count
            ORDER BY PATIENT_COUNT DESC
            """
        else:  # MEDICATION
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND ethnicity_subcategory IS NOT NULL
            )
            SELECT 
                d.ethnicity_subcategory AS ETHNICITY,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.ethnicity_subcategory IS NOT NULL
            GROUP BY d.ethnicity_subcategory, tp.total_count
            ORDER BY PATIENT_COUNT DESC
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading ethnicity analysis: {str(e)}")
        return pd.DataFrame()


def get_cluster_deprivation_analysis(cluster_id, cluster_type, source=None):
    """Get deprivation (IMD) breakdown for patients with codes in cluster"""
    try:
        code_src = _code_source(source)
        # Choose table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND imd_decile_19 IS NOT NULL
            )
            SELECT 
                d.imd_decile_19 AS IMD_DECILE,
                d.imd_quintile_19 AS IMD_QUINTILE,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.imd_decile_19 IS NOT NULL
            GROUP BY d.imd_decile_19, d.imd_quintile_19, tp.total_count
            ORDER BY d.imd_decile_19
            """
        else:  # MEDICATION
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND imd_decile_19 IS NOT NULL
            )
            SELECT 
                d.imd_decile_19 AS IMD_DECILE,
                d.imd_quintile_19 AS IMD_QUINTILE,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.imd_decile_19 IS NOT NULL
            GROUP BY d.imd_decile_19, d.imd_quintile_19, tp.total_count
            ORDER BY d.imd_decile_19
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading deprivation analysis: {str(e)}")
        return pd.DataFrame()


def get_cluster_language_analysis(cluster_id, cluster_type, source=None):
    """Get language breakdown for patients with codes in cluster"""
    try:
        code_src = _code_source(source)
        # Choose table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            SELECT 
                d.language_type AS LANGUAGE_TYPE,
                d.main_language AS MAIN_LANGUAGE,
                d.interpreter_needed AS INTERPRETER_NEEDED,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT
            FROM {DB_STORE}.observation o
            JOIN {code_src} ec ON o.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.main_language IS NOT NULL
            GROUP BY d.language_type, d.main_language, d.interpreter_needed
            ORDER BY PATIENT_COUNT DESC
            """
        else:  # MEDICATION
            query = f"""
            SELECT 
                d.language_type AS LANGUAGE_TYPE,
                d.main_language AS MAIN_LANGUAGE,
                d.interpreter_needed AS INTERPRETER_NEEDED,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT
            FROM {DB_STORE}.medication_order mo
            JOIN {code_src} ec ON mo.mapped_concept_code = ec.code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.main_language IS NOT NULL
            GROUP BY d.language_type, d.main_language, d.interpreter_needed
            ORDER BY PATIENT_COUNT DESC
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading language analysis: {str(e)}")
        return pd.DataFrame()


def get_cluster_neighbourhood_analysis(cluster_id, cluster_type, source=None):
    """Get neighbourhood breakdown for patients with codes in cluster"""
    try:
        code_src = _code_source(source)
        # Choose table based on cluster type
        if cluster_type == 'OBSERVATION':
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND neighbourhood_registered IS NOT NULL
            )
            SELECT 
                d.neighbourhood_registered AS NEIGHBOURHOOD,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                AVG(d.age) AS AVG_AGE,
                AVG(d.imd_decile_19) AS AVG_IMD_DECILE,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.observation o ON ec.code = o.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON o.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.neighbourhood_registered IS NOT NULL
            GROUP BY d.neighbourhood_registered, tp.total_count
            ORDER BY PATIENT_COUNT DESC
            """
        else:  # MEDICATION
            query = f"""
            WITH total_pop AS (
                SELECT COUNT(DISTINCT person_id) AS total_count
                FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS 
                WHERE is_active = true 
                AND neighbourhood_registered IS NOT NULL
            )
            SELECT 
                d.neighbourhood_registered AS NEIGHBOURHOOD,
                COUNT(DISTINCT d.person_id) AS PATIENT_COUNT,
                AVG(d.age) AS AVG_AGE,
                AVG(d.imd_decile_19) AS AVG_IMD_DECILE,
                COUNT(DISTINCT d.person_id) * 1000.0 / tp.total_count AS RATE_PER_1000
            FROM {code_src} ec
            JOIN {DB_STORE}.medication_order mo ON ec.code = mo.mapped_concept_code
            JOIN {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS d ON mo.person_id = d.person_id
            CROSS JOIN total_pop tp
            WHERE ec.cluster_id = '{cluster_id}'
            AND d.is_active = true
            AND d.neighbourhood_registered IS NOT NULL
            GROUP BY d.neighbourhood_registered, tp.total_count
            ORDER BY PATIENT_COUNT DESC
            """
        
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading neighbourhood analysis: {str(e)}")
        return pd.DataFrame()