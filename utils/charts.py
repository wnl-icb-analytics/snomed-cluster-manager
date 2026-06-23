# =============================================================================
# SNOMED Cluster Manager - Chart Utilities
# =============================================================================

import pandas as pd
import altair as alt
import streamlit as st


def create_population_pyramid(df):
    """Create a population pyramid chart from age/sex distribution data
    
    Args:
        df: DataFrame with AGE_BAND, SEX, and PATIENT_COUNT columns
    """
    if df.empty:
        st.warning("No data available for population pyramid")
        return
    
    # Prepare data for pyramid (males negative, females positive)
    pyramid_data = df.copy()
    pyramid_data['DISPLAY_COUNT'] = pyramid_data['PATIENT_COUNT'].copy()  # Keep original for tooltip
    pyramid_data.loc[pyramid_data['SEX'] == 'Male', 'PATIENT_COUNT'] = -pyramid_data.loc[pyramid_data['SEX'] == 'Male', 'PATIENT_COUNT']
    
    # Calculate max value for symmetric axis
    max_val = pyramid_data['DISPLAY_COUNT'].max()
    
    # Extract numeric age for sorting; drop bands without a number (e.g. 'Unknown')
    pyramid_data['AGE_SORT'] = pyramid_data['AGE_BAND'].str.extract(r'(\d+)')[0]
    pyramid_data = pyramid_data.dropna(subset=['AGE_SORT'])
    pyramid_data['AGE_SORT'] = pyramid_data['AGE_SORT'].astype(int)
    
    # Set labels
    x_title = "Active Patients"
    tooltip_title = "Active Patients"  
    chart_title = "Population Pyramid by Age and Sex"
    
    # Create the pyramid chart
    pyramid_chart = alt.Chart(pyramid_data).mark_bar().add_selection(
        alt.selection_interval(bind='scales')
    ).encode(
        x=alt.X('PATIENT_COUNT:Q', 
               title=x_title,
               axis=alt.Axis(format='d', labelExpr='abs(datum.value)'),
               scale=alt.Scale(domain=[-max_val, max_val])),
        y=alt.Y('AGE_BAND:O', title='Age Group', sort=alt.EncodingSortField(field='AGE_SORT', order='descending')),
        color=alt.Color('SEX:N', 
                       scale=alt.Scale(domain=['Male', 'Female'], 
                                     range=['#1f77b4', '#ff7f0e']),
                       title='Sex'),
        tooltip=[
            alt.Tooltip('AGE_BAND:O', title='Age Group'), 
            alt.Tooltip('SEX:N', title='Sex'), 
            alt.Tooltip('DISPLAY_COUNT:Q', format=',.0f', title=tooltip_title)
        ]
    ).properties(
        width=600,
        height=400,
        title=chart_title
    )
    
    st.altair_chart(pyramid_chart, use_container_width=True)


def create_rates_scatter_plot(df, agg_level):
    """Create scatter plot for standardized rates"""
    if df.empty:
        return alt.Chart().mark_text(
            text="No data available",
            fontSize=16
        )
    
    chart = alt.Chart(df).mark_circle(
        size=100,
        opacity=0.7
    ).encode(
        x=alt.X('EXPECTED_COUNT:Q', 
                title='Expected Count',
                scale=alt.Scale(type='log')),
        y=alt.Y('OBSERVED_COUNT:Q', 
                title='Observed Count',
                scale=alt.Scale(type='log')),
        color=alt.Color('SIR:Q',
                       title='SIR',
                       scale=alt.Scale(scheme='viridis')),
        size=alt.Size('POPULATION:Q',
                     title='Population Size',
                     scale=alt.Scale(range=[50, 400])),
        tooltip=[
            alt.Tooltip(f'{agg_level.upper()}:N', title=agg_level),
            alt.Tooltip('OBSERVED_COUNT:Q', title='Observed', format='.0f'),
            alt.Tooltip('EXPECTED_COUNT:Q', title='Expected', format='.2f'),
            alt.Tooltip('SIR:Q', title='SIR', format='.2f'),
            alt.Tooltip('POPULATION:Q', title='Population', format='.0f')
        ]
    ).properties(
        width=500,
        height=400,
        title=f'Observed vs Expected Counts by {agg_level}'
    )
    
    # Add reference line (y = x)
    line_data = pd.DataFrame({
        'x': [df['EXPECTED_COUNT'].min(), df['EXPECTED_COUNT'].max()],
        'y': [df['EXPECTED_COUNT'].min(), df['EXPECTED_COUNT'].max()]
    })
    
    reference_line = alt.Chart(line_data).mark_line(
        color='red',
        strokeDash=[5, 5],
        opacity=0.7
    ).encode(
        x='x:Q',
        y='y:Q'
    )
    
    return chart + reference_line


def create_org_bar_chart(df, agg_level):
    """Create horizontal bar chart for organizational data"""
    if df.empty:
        return alt.Chart().mark_text(
            text="No data available",
            fontSize=16
        )
    
    # Limit to top 20 for readability
    df_limited = df.head(20).copy()
    
    chart = alt.Chart(df_limited).mark_bar().encode(
        x=alt.X('PERSON_COUNT:Q', 
                title='Number of Persons'),
        y=alt.Y(f'{agg_level.upper()}:N', 
                title=agg_level,
                sort='-x'),
        color=alt.Color('PERSON_COUNT:Q',
                       scale=alt.Scale(scheme='blues'),
                       legend=None),
        tooltip=[
            alt.Tooltip(f'{agg_level.upper()}:N', title=agg_level),
            alt.Tooltip('PERSON_COUNT:Q', title='Persons', format='.0f')
        ]
    ).properties(
        width=500,
        height=max(300, len(df_limited) * 20),
        title=f'Person Count by {agg_level} (Top 20)'
    )
    
    return chart


def create_practice_scatter(df):
    """Create scatter plot for practice-level data showing age vs rate"""
    if df.empty:
        return None
    
    # Calculate average rate for reference line
    avg_rate = df['RATE_PER_1000'].mean()
    
    # Create scatter plot
    scatter = alt.Chart(df).mark_circle().encode(
        x=alt.X('AVG_AGE:Q', 
                title='Average Age',
                scale=alt.Scale(domain=[df['AVG_AGE'].min() - 2, df['AVG_AGE'].max() + 2])),
        y=alt.Y('RATE_PER_1000:Q', 
                title='Rate per 1,000 population'),
        size=alt.Size('PATIENTS_WITH_CODE:Q',
                     title='Patients with Code',
                     scale=alt.Scale(range=[20, 400])),
        color=alt.Color('RATE_PER_1000:Q',
                       scale=alt.Scale(scheme='orangered'),
                       title='Rate'),
        tooltip=[
            alt.Tooltip('UNIT_NAME:N', title='Practice'),
            alt.Tooltip('AVG_AGE:Q', format='.1f', title='Avg Age'),
            alt.Tooltip('TOTAL_POPULATION:Q', format=',.0f', title='Population'),
            alt.Tooltip('PATIENTS_WITH_CODE:Q', format=',.0f', title='Patients with Code'),
            alt.Tooltip('RATE_PER_1000:Q', format='.2f', title='Rate per 1,000')
        ]
    ).properties(
        width=600,
        height=400,
        title='Practice Analysis: Age vs Rate'
    )
    
    # Add horizontal reference line for average rate
    rule = alt.Chart(pd.DataFrame({'avg': [avg_rate]})).mark_rule(
        color='red',
        strokeDash=[5, 5],
        opacity=0.7
    ).encode(
        y='avg:Q'
    )
    
    # Add text label for reference line
    text = alt.Chart(pd.DataFrame({'avg': [avg_rate], 'label': [f'Avg: {avg_rate:.1f}']})).mark_text(
        align='right',
        dx=-10,
        dy=-5,
        color='red',
        fontSize=10
    ).encode(
        x=alt.value(590),  # Position at right edge
        y='avg:Q',
        text='label:N'
    )
    
    return scatter + rule + text


def create_age_slope_chart(df):
    """Create an area chart showing age distribution without gender split
    
    Args:
        df: DataFrame with AGE_BAND, SEX, and PATIENT_COUNT columns
    """
    if df.empty:
        st.warning("No data available for age slope chart")
        return
    
    # Aggregate by age band (combine both genders)
    age_data = df.groupby('AGE_BAND')['PATIENT_COUNT'].sum().reset_index()
    
    # Extract numeric age for sorting; drop bands without a number (e.g. 'Unknown')
    age_data['AGE_SORT'] = age_data['AGE_BAND'].str.extract(r'(\d+)')[0]
    age_data = age_data.dropna(subset=['AGE_SORT'])
    age_data['AGE_SORT'] = age_data['AGE_SORT'].astype(int)
    age_data = age_data.sort_values('AGE_SORT')
    
    # Set labels
    y_title = "Active Patients"
    tooltip_title = "Active Patients"
    chart_title = "Age Distribution (Active Patients)"
    
    # Create bar chart
    area_chart = alt.Chart(age_data).mark_bar().encode(
        x=alt.X('AGE_BAND:O', 
               title='Age Group',
               sort=alt.EncodingSortField(field='AGE_SORT', order='ascending')),
        y=alt.Y('PATIENT_COUNT:Q', 
               title=y_title),
        tooltip=[
            alt.Tooltip('AGE_BAND:O', title='Age Group'),
            alt.Tooltip('PATIENT_COUNT:Q', format=',.0f', title=tooltip_title)
        ]
    ).properties(
        width=600,
        height=300,
        title=chart_title
    )
    
    st.altair_chart(area_chart, use_container_width=True)


def create_ethnicity_bar_chart(df):
    """Create horizontal bar chart for ethnicity analysis"""
    if df.empty:
        st.warning("No ethnicity data available")
        return
    
    # Calculate percentages
    df_with_pct = df.copy()
    total_patients = df_with_pct['PATIENT_COUNT'].sum()
    df_with_pct['PERCENTAGE'] = (df_with_pct['PATIENT_COUNT'] / total_patients * 100)
    
    chart = alt.Chart(df_with_pct).mark_bar().encode(
        x=alt.X('PERCENTAGE:Q', 
                title='Percentage of Patients'),
        y=alt.Y('ETHNICITY:N', 
                title='Ethnicity',
                sort='-x'),
        color=alt.Color('RATE_PER_1000:Q',
                       scale=alt.Scale(scheme='blues'),
                       title='Rate per 1,000'),
        tooltip=[
            alt.Tooltip('ETHNICITY:N', title='Ethnicity'),
            alt.Tooltip('PATIENT_COUNT:Q', format=',.0f', title='Patients'),
            alt.Tooltip('PERCENTAGE:Q', format='.1f', title='Percentage'),
            alt.Tooltip('RATE_PER_1000:Q', format='.2f', title='Rate per 1,000')
        ]
    ).properties(
        width=600,
        height=max(300, len(df_with_pct) * 25),
        title='Ethnicity Distribution'
    )
    
    st.altair_chart(chart, use_container_width=True)


def create_deprivation_bar_chart(df):
    """Create bar chart showing deprivation gradient by IMD decile"""
    if df.empty:
        st.warning("No deprivation data available")
        return

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('IMD_DECILE:O',
               title='IMD Decile (1=Most Deprived, 10=Least Deprived)'),
        y=alt.Y('RATE_PER_1000:Q',
               title='Rate per 1,000 population'),
        color=alt.Color('RATE_PER_1000:Q',
                       scale=alt.Scale(scheme='blues'),
                       legend=None),
        tooltip=[
            alt.Tooltip('IMD_DECILE:O', title='IMD Decile'),
            alt.Tooltip('IMD_QUINTILE:N', title='IMD Quintile'),
            alt.Tooltip('PATIENT_COUNT:Q', format=',.0f', title='Patients'),
            alt.Tooltip('RATE_PER_1000:Q', format='.2f', title='Rate per 1,000')
        ]
    ).properties(
        width=600,
        height=300,
        title='Social Gradient: Prevalence by Deprivation Decile'
    )

    st.altair_chart(chart, use_container_width=True)


def create_language_bar_chart(df):
    """Create horizontal bar chart for language distribution"""
    if df.empty:
        st.warning("No language data available")
        return
    
    # Aggregate by language
    lang_summary = df.groupby('MAIN_LANGUAGE')['PATIENT_COUNT'].sum().reset_index()
    
    # Calculate percentages
    total_patients = lang_summary['PATIENT_COUNT'].sum()
    lang_summary['PERCENTAGE'] = (lang_summary['PATIENT_COUNT'] / total_patients * 100)
    
    # Sort and limit to top 15 for readability
    lang_limited = lang_summary.sort_values('PATIENT_COUNT', ascending=False).head(15).copy()
    
    chart = alt.Chart(lang_limited).mark_bar().encode(
        x=alt.X('PERCENTAGE:Q', 
                title='Percentage of Patients'),
        y=alt.Y('MAIN_LANGUAGE:N', 
                title='Language',
                sort='-x'),
        tooltip=[
            alt.Tooltip('MAIN_LANGUAGE:N', title='Language'),
            alt.Tooltip('PATIENT_COUNT:Q', format=',.0f', title='Patients'),
            alt.Tooltip('PERCENTAGE:Q', format='.1f', title='Percentage')
        ]
    ).properties(
        width=600,
        height=max(300, len(lang_limited) * 25),
        title='Language Distribution (Top 15)'
    )
    
    st.caption("Only includes patients with recorded language data")
    st.altair_chart(chart, use_container_width=True)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    total_patients_with_lang = df['PATIENT_COUNT'].sum()
    english_patients = df[df['MAIN_LANGUAGE'] == 'English']['PATIENT_COUNT'].sum()
    not_recorded_patients = df[df['MAIN_LANGUAGE'] == 'Not Recorded']['PATIENT_COUNT'].sum() if 'Not Recorded' in df['MAIN_LANGUAGE'].values else 0
    
    # Calculate total including those with no language recorded
    total_all_patients = total_patients_with_lang  # This is all patients in the cluster with language data
    patients_with_recorded_lang = total_patients_with_lang - not_recorded_patients
    
    with col1:
        if total_all_patients > 0:
            lang_coverage_pct = (patients_with_recorded_lang / total_all_patients * 100)
            st.metric("Language Data Coverage", f"{lang_coverage_pct:.1f}%",
                     help="Percentage of patients with language recorded (excluding 'Not Recorded')")
        else:
            st.metric("Language Data Coverage", "0.0%")
    
    with col2:
        if patients_with_recorded_lang > 0:
            recorded_non_english_pct = ((patients_with_recorded_lang - english_patients) / patients_with_recorded_lang * 100)
            st.metric("Main Language Not English", f"{recorded_non_english_pct:.1f}%", 
                     help="Of patients with recorded language data")
        else:
            st.metric("Main Language Not English", "0.0%")
    
    with col3:
        unique_languages = len([lang for lang in df['MAIN_LANGUAGE'].unique() if lang != 'Not Recorded'])
        st.metric("Languages Represented", unique_languages)


def create_neighbourhood_bar_chart(df):
    """Create horizontal bar chart for neighbourhood comparison"""
    if df.empty:
        st.warning("No neighbourhood data available")
        return
    
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('RATE_PER_1000:Q', 
                title='Rate per 1,000 population'),
        y=alt.Y('NEIGHBOURHOOD:N', 
                title='Neighbourhood',
                sort='-x'),
        color=alt.Color('PATIENT_COUNT:Q',
                       scale=alt.Scale(scheme='blues'),
                       title='Patient Count'),
        tooltip=[
            alt.Tooltip('NEIGHBOURHOOD:N', title='Neighbourhood'),
            alt.Tooltip('PATIENT_COUNT:Q', format=',.0f', title='Patients'),
            alt.Tooltip('RATE_PER_1000:Q', format='.2f', title='Rate per 1,000'),
            alt.Tooltip('AVG_AGE:Q', format='.1f', title='Avg Age')
        ]
    ).properties(
        width=600,
        height=max(300, len(df) * 30),
        title='Neighbourhood Comparison'
    )
    
    st.altair_chart(chart, use_container_width=True)