from config import AUTHORED_SOURCE, CODESETS_TABLE


def codeset_filter(cluster_id, source=None, alias=None):
    """Select one published codeset by its source and cluster ID."""
    safe_id = str(cluster_id).replace("'", "''")
    safe_source = str(source or AUTHORED_SOURCE).replace("'", "''")
    prefix = f"{alias}." if alias else ""
    return (
        f"{prefix}cluster_id = '{safe_id}' "
        f"AND {prefix}source = '{safe_source}'"
    )


def codeset_codes_query(cluster_id, source=None):
    """SQL for analysts to retrieve published code membership."""
    return f"""SELECT code, code_description, source
FROM {CODESETS_TABLE}
WHERE {codeset_filter(cluster_id, source)}
ORDER BY code;"""


def codeset_code_source(source=None):
    """Published membership with the display column used by analytics."""
    safe_source = str(source or AUTHORED_SOURCE).replace("'", "''")
    return (
        f"(SELECT code, code_description AS display, cluster_id "
        f"FROM {CODESETS_TABLE} WHERE source = '{safe_source}')"
    )
