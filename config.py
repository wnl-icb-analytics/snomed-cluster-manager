# =============================================================================
# SNOMED Cluster Manager - Configuration & Constants
# =============================================================================

# Labels
STALE_LABEL = "Stale (>28 days)"

# Database configuration
DB_SCHEMA = "DATA_LAKE__NCL.TERMINOLOGY"
DB_ANALYTICS = "REPORTING"
DB_STORE = "DATA_LAKE.OLIDS"
DB_DEMOGRAPHICS = "REPORTING.OLIDS_PERSON_DEMOGRAPHICS"

# Role and warehouse
ROLE = "ISL-USERGROUP-SECONDEES-NCL"
WAREHOUSE = "WH_NCL_ENGINEERING_XS"

# Page configuration
PAGE_CONFIG = {
    "page_title": "SNOMED Cluster Manager",
    "page_icon": "🧬",
    "layout": "wide",
    "initial_sidebar_state": "collapsed"
}

# Cluster type mappings
CLUSTER_TYPE_DISPLAY = {
    'OBSERVATION': '[observation]',
    'MEDICATION': '[medication]'
}

# Status emojis
STATUS_EMOJI = {
    'error': '❌',
    'stale': '⚠️',
    'new': '🆕',
    'fresh': '✅'
}

# Custom CSS for ECL expression styling
CUSTOM_CSS = """
<style>
/* Style pipe-delimited SNOMED concept descriptions within code blocks */
.stCodeBlock code {
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

/* Target the concept descriptions between pipes */
.stCodeBlock .concept-desc {
    color: #888888 !important;
    font-style: italic;
}

.stCodeBlock .pipe-char {
    color: #aaaaaa !important;
}

/* Style the navigation buttons */
.nav-button {
    width: 100%;
    margin-bottom: 5px;
    text-align: left;
    background: #f0f2f6;
    border: 1px solid #e6e9ef;
    border-radius: 5px;
    padding: 8px 12px;
    transition: all 0.3s ease;
}

.nav-button:hover {
    background: #e6e9ef;
    border-color: #d4dae6;
}

/* Primary buttons: solid accent fill with white text in ALL states.
   Fixes SiS default rendering that showed the accent as text on a transparent
   fill until hover (looked like the colours were inverted). */
button[kind="primary"],
button[kind="primaryFormSubmit"],
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
    background-color: #3b82f6 !important;
    border: 1px solid #3b82f6 !important;
    color: #ffffff !important;
}
button[kind="primary"]:hover,
button[kind="primaryFormSubmit"]:hover,
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background-color: #2f6ae0 !important;
    border-color: #2f6ae0 !important;
    color: #ffffff !important;
}

/* Secondary buttons: normal text by default, accent only on hover */
button[kind="secondary"]:hover,
button[data-testid="stBaseButton-secondary"]:hover {
    border-color: #3b82f6 !important;
    color: #3b82f6 !important;
}
</style>
"""