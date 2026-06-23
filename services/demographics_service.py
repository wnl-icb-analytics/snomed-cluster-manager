# =============================================================================
# SNOMED Cluster Manager - Demographics Service
# =============================================================================

import pandas as pd
import streamlit as st
from database import get_connection
from config import DB_DEMOGRAPHICS


# Get connection instance
conn = get_connection()


def get_demographics_summary():
    """Get overall population demographics summary"""
    try:
        query = f"""
        SELECT 
            COUNT(DISTINCT person_id) as total_active_patients,
            COUNT(DISTINCT practice_code) as total_practices,
            COUNT(DISTINCT pcn_code) as total_pcns,
            AVG(age) as avg_age,
            COUNT(CASE WHEN gender = 'Male' THEN 1 END) as male_count,
            COUNT(CASE WHEN gender = 'Female' THEN 1 END) as female_count
        FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
        WHERE is_active = true
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading demographics summary: {str(e)}")
        return pd.DataFrame()


def get_demographics_by_care_team(care_team_level):
    """Get demographics breakdown by care team level"""
    try:
        # Determine aggregation field and name based on care team level
        if care_team_level == "PCN":
            agg_field = "pcn_code"
            name_field = "pcn_name"
        elif care_team_level == "Practice":
            agg_field = "practice_code" 
            name_field = "practice_name"
        else:  # System level
            agg_field = "'System'"
            name_field = "'Overall Population'"
            
        query = f"""
        SELECT
            {agg_field} as care_team_code,
            {name_field} as care_team_name,
            age_band_5y AS AGE_BAND,
            gender AS SEX,
            COUNT(*) as patient_count
        FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
        WHERE is_active = true
        AND {agg_field} IS NOT NULL
        GROUP BY {agg_field}, {name_field}, age_band_5y, gender
        ORDER BY care_team_code, age_band_5y, gender
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading care team demographics: {str(e)}")
        return pd.DataFrame()


def get_care_team_summary(care_team_level):
    """Get summary statistics by care team"""
    try:
        if care_team_level == "PCN":
            agg_field = "pcn_code"
            name_field = "pcn_name"
        elif care_team_level == "Practice":
            agg_field = "practice_code"
            name_field = "practice_name"
        else:  # System level
            return get_demographics_summary()
            
        query = f"""
        SELECT 
            {agg_field} as care_team_code,
            {name_field} as care_team_name,
            COUNT(DISTINCT person_id) as total_patients,
            AVG(age) as avg_age,
            COUNT(CASE WHEN gender = 'Male' THEN 1 END) as male_count,
            COUNT(CASE WHEN gender = 'Female' THEN 1 END) as female_count,
            COUNT(CASE WHEN age_band_5y IN ('0-4', '5-9', '10-14') THEN 1 END) as children_count,
            COUNT(CASE WHEN age_band_5y IN ('65-69', '70-74', '75-79', '80-84', '85+') THEN 1 END) as elderly_count
        FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
        WHERE is_active = true
        AND {agg_field} IS NOT NULL
        GROUP BY {agg_field}, {name_field}
        ORDER BY total_patients DESC
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading care team summary: {str(e)}")
        return pd.DataFrame()


def get_system_age_sex_distribution():
    """Get system-wide age/sex distribution for standardization"""
    try:
        query = f"""
        SELECT
            age_band_5y AS AGE_BAND,
            gender AS SEX,
            COUNT(*) as patient_count,
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
        FROM {DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS
        WHERE is_active = true
        AND gender IN ('Male', 'Female')
        GROUP BY age_band_5y, gender
        ORDER BY age_band_5y, gender
        """
        return conn.sql(query).to_pandas()
    except Exception as e:
        st.error(f"Error loading system distribution: {str(e)}")
        return pd.DataFrame()