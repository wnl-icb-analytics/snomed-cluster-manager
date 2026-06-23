# =============================================================================
# SNOMED Cluster Manager - Home Page
# Single search across all codesets: authored here + brought in
# =============================================================================

import streamlit as st
import pandas as pd
from database import rerun
from components.cluster_components import render_flash_message
from services.codeset_service import get_codeset_index, source_label
from config import CLUSTER_TYPE_DISPLAY

RENDER_CAP = 100  # max rows rendered at once; users refine with search


def _open_codeset(source, cluster_id, page):
    """Select a codeset and navigate to one of its pages."""
    st.session_state.selected_cluster = cluster_id
    st.session_state.selected_source = source
    st.session_state.pop('codeset_mode', None)  # reset analysis mode per codeset
    st.session_state.page = page
    rerun()


def render_home():
    """Home page: search across authored and brought-in codesets."""
    render_flash_message()

    st.markdown(
        "Search every codeset - those we **author** here and those we **bring in** "
        "(PCD/GDPPR, OpenCodelists, LTC LCS, UKHSA, immunisations, QAdmissions)."
    )

    try:
        index_df = get_codeset_index()
    except Exception as e:
        st.error(f"⚠️ Database connection error: {str(e)}")
        index_df = pd.DataFrame()

    if index_df.empty:
        st.info("🌟 **Welcome!** No codesets found. Author one with **✨ Add New** above.")
        return

    authored_df = index_df[index_df['IS_AUTHORED'] == True]
    brought_df = index_df[index_df['IS_AUTHORED'] == False]

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Authored", f"{len(authored_df):,}")
    c2.metric("Brought-in", f"{len(brought_df):,}")
    c3.metric("Total codes", f"{int(index_df['CODE_COUNT'].fillna(0).sum()):,}")

    st.markdown("---")

    # Search + scope
    col_s, col_f = st.columns([3, 2])
    with col_s:
        search_term = st.text_input(
            "Search codesets", placeholder="Search by id or description...",
            key="home_search", label_visibility="collapsed"
        )
    with col_f:
        scope = st.radio(
            "Show", options=["Authored", "Brought-in", "All"],
            horizontal=True, index=0, key="home_scope", label_visibility="collapsed"
        )

    df = index_df
    if scope == "Authored":
        df = authored_df
    elif scope == "Brought-in":
        df = brought_df

    # Source filter for brought-in codesets
    if scope in ("Brought-in", "All"):
        sources = sorted(brought_df['SOURCE'].unique().tolist())
        chosen = st.multiselect(
            "Filter by source", options=sources, default=[],
            format_func=source_label, key="home_sources",
            help="Limit brought-in codesets to specific sources"
        )
        if chosen:
            df = df[df['IS_AUTHORED'] | df['SOURCE'].isin(chosen)] if scope == "All" else df[df['SOURCE'].isin(chosen)]

    if search_term:
        mask = (df['CLUSTER_ID'].str.contains(search_term, case=False, na=False) |
                df['DESCRIPTION'].fillna('').str.contains(search_term, case=False, na=False))
        df = df[mask]

    total = len(df)
    if total == 0:
        st.info("No codesets match your search.")
        return

    # Authored first, then alphabetical; cap rendering for performance
    df = df.sort_values(['IS_AUTHORED', 'CLUSTER_ID'], ascending=[False, True])
    shown = df.head(RENDER_CAP)
    note = "  ·  refine your search to narrow further" if total > RENDER_CAP else ""
    st.caption(f"Showing {len(shown)} of {total:,} codeset(s){note}")

    for _, row in shown.iterrows():
        is_authored = bool(row['IS_AUTHORED'])
        source = row['SOURCE']
        cid = row['CLUSTER_ID']

        col1, col2, col3, col4 = st.columns([3.6, 1.6, 1.8, 1.0])
        with col1:
            badge = "✍️ Authored" if is_authored else f"📥 {source_label(source)}"
            st.markdown(
                f"**{cid}** <small style='color:#888;'>{badge}</small>",
                unsafe_allow_html=True
            )
            if pd.notna(row.get('DESCRIPTION')) and row.get('DESCRIPTION'):
                st.caption(str(row['DESCRIPTION']))
        with col2:
            cc = int(row['CODE_COUNT']) if not pd.isna(row['CODE_COUNT']) else 0
            st.text(f"{cc:,} codes")
        with col3:
            if is_authored:
                st.caption(CLUSTER_TYPE_DISPLAY.get(row.get('CLUSTER_TYPE', 'OBSERVATION'), '[observation]'))
            else:
                st.caption("read-only")
        with col4:
            b1, b2 = st.columns(2)
            with b1:
                if st.button("👁️", key=f"view_{source}_{cid}", help="View details"):
                    _open_codeset(source, cid, 'details')
            with b2:
                if is_authored and st.button("✏️", key=f"edit_{source}_{cid}", help="Edit"):
                    _open_codeset(source, cid, 'edit')

        st.markdown("<div style='margin:6px 0;'></div>", unsafe_allow_html=True)
