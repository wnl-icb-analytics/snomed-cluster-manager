# =============================================================================
# SNOMED Cluster Manager - Home Page
# Single search across all codesets: authored here + brought in
# =============================================================================

import math
import streamlit as st
import pandas as pd
from database import rerun
from components.cluster_components import render_flash_message
from services.codeset_service import get_codeset_index, source_label
from config import CLUSTER_TYPE_DISPLAY

PAGE_SIZE = 50  # codesets rendered per page


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
    chosen = []
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

    # Authored first, then alphabetical
    df = df.sort_values(['IS_AUTHORED', 'CLUSTER_ID'], ascending=[False, True])

    # Paginate. Reset to page 1 whenever the filter changes.
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    sig = (search_term, scope, tuple(sorted(chosen)))
    if st.session_state.get('home_sig') != sig:
        st.session_state['home_sig'] = sig
        st.session_state['home_page'] = 1
    page = max(1, min(st.session_state.get('home_page', 1), total_pages))
    st.session_state['home_page'] = page

    if total_pages > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("← Prev", disabled=page <= 1, use_container_width=True):
                st.session_state['home_page'] = page - 1
                rerun()
        with pc2:
            jump = st.number_input(
                "Page", min_value=1, max_value=total_pages, value=page, step=1,
                label_visibility="collapsed"
            )
            if int(jump) != page:
                st.session_state['home_page'] = int(jump)
                rerun()
        with pc3:
            if st.button("Next →", disabled=page >= total_pages, use_container_width=True):
                st.session_state['home_page'] = page + 1
                rerun()

    start = (page - 1) * PAGE_SIZE
    shown = df.iloc[start:start + PAGE_SIZE]
    st.caption(
        f"Showing {start + 1:,}-{min(start + PAGE_SIZE, total):,} of {total:,} codeset(s)"
        f"  ·  page {page} of {total_pages}"
    )

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
