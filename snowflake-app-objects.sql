-- =============================================================================
-- SNOMED Cluster Manager - Snowflake application objects
-- =============================================================================
-- Source of truth for the tables, local functions and procedures directly used
-- by the Streamlit app.
--
-- External dependency intentionally not managed here:
--   EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS(ecl_expression, branch)
--
-- Data products queried by the app but owned by separate pipelines:
--   DATA_LAKE__NCL.TERMINOLOGY.COMBINED_CODESETS
--   DATA_LAKE.OLIDS.OBSERVATION
--   DATA_LAKE.OLIDS.MEDICATION_ORDER
--   REPORTING.OLIDS_PERSON_DEMOGRAPHICS.DIM_PERSON_DEMOGRAPHICS
--
-- Run with:
--   snow sql -c ENGINEER -f snowflake-app-objects.sql
-- =============================================================================

USE DATABASE DATA_LAKE__NCL;
USE SCHEMA TERMINOLOGY;

-- =============================================================================
-- Core tables
-- =============================================================================

CREATE TABLE IF NOT EXISTS ECL_CLUSTERS (
    CLUSTER_ID VARCHAR,
    ECL_EXPRESSION VARCHAR,
    DESCRIPTION VARCHAR,
    CREATED_AT TIMESTAMP_NTZ,
    UPDATED_AT TIMESTAMP_NTZ,
    CREATED_BY VARCHAR,
    UPDATED_BY VARCHAR,
    CLUSTER_TYPE VARCHAR,
    CLUSTER_UID VARCHAR
);

CREATE TABLE IF NOT EXISTS ECL_CACHE (
    CLUSTER_ID VARCHAR,
    CODE VARCHAR,
    DISPLAY VARCHAR,
    SYSTEM VARCHAR,
    LAST_REFRESHED TIMESTAMP_NTZ,
    ECL_EXPRESSION_HASH VARCHAR
);

CREATE TABLE IF NOT EXISTS ECL_CACHE_METADATA (
    CLUSTER_ID VARCHAR,
    LAST_SUCCESSFUL_REFRESH TIMESTAMP_NTZ,
    LAST_ATTEMPTED_REFRESH TIMESTAMP_NTZ,
    ECL_EXPRESSION_HASH VARCHAR,
    RECORD_COUNT NUMBER,
    LAST_REFRESHED_BY VARCHAR,
    LAST_ATTEMPTED_BY VARCHAR,
    LAST_ERROR_MESSAGE VARCHAR
);

CREATE TABLE IF NOT EXISTS ECL_CLUSTER_CHANGES (
    CHANGE_ID NUMBER AUTOINCREMENT,
    CLUSTER_ID VARCHAR,
    CHANGE_TYPE VARCHAR,
    CODE VARCHAR,
    DISPLAY VARCHAR,
    SYSTEM VARCHAR,
    CHANGE_TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CHANGED_BY VARCHAR,
    REFRESH_SESSION_ID VARCHAR
);

ALTER TABLE ECL_CLUSTERS
    ADD COLUMN IF NOT EXISTS CLUSTER_UID VARCHAR;

UPDATE ECL_CLUSTERS
SET CLUSTER_UID = UUID_STRING()
WHERE CLUSTER_UID IS NULL;

-- =============================================================================
-- Local functions
-- =============================================================================

CREATE OR REPLACE FUNCTION ECL_EXPRESSION_HASH(ECL_EXPRESSION VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
    SELECT SHA2(
        UPPER(
            TRIM(
                REPLACE(
                    REPLACE(ecl_expression, CHR(10), ' '),
                    CHR(13),
                    ' '
                )
            )
        ),
        256
    )
$$;

CREATE OR REPLACE FUNCTION ECL_CACHED_CODES(CLUSTER_ID VARCHAR)
RETURNS TABLE (CODE VARCHAR)
LANGUAGE SQL
AS
$$
    SELECT code
    FROM ECL_CACHE
    WHERE cluster_id = $1
$$;

CREATE OR REPLACE FUNCTION ECL_CACHED_DETAILS(CLUSTER_ID VARCHAR)
RETURNS TABLE (
    CODE VARCHAR,
    DISPLAY VARCHAR,
    SYSTEM VARCHAR,
    LAST_REFRESHED TIMESTAMP_NTZ
)
LANGUAGE SQL
AS
$$
    SELECT code, display, system, last_refreshed
    FROM ECL_CACHE
    WHERE cluster_id = $1
$$;

CREATE OR REPLACE FUNCTION ECL_TEST_DETAILS(ECL_EXPRESSION VARCHAR)
RETURNS TABLE (CODE VARCHAR, DISPLAY VARCHAR, SYSTEM VARCHAR)
LANGUAGE SQL
AS
$$
    SELECT code, display, system
    FROM TABLE(
        EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS(ecl_expression, 'production1')
    )
    LIMIT 50000
$$;

-- =============================================================================
-- Append-only definition versioning
-- =============================================================================

CREATE TABLE IF NOT EXISTS ECL_CLUSTER_VERSIONS (
    VERSION_ID VARCHAR NOT NULL,
    VERSION_HASH VARCHAR NOT NULL,
    CONTENT_HASH VARCHAR NOT NULL,
    ECL_EXPRESSION_HASH VARCHAR,
    CLUSTER_UID VARCHAR NOT NULL,
    CLUSTER_ID VARCHAR NOT NULL,
    VERSION_NUMBER NUMBER NOT NULL,
    ECL_EXPRESSION VARCHAR,
    DESCRIPTION VARCHAR,
    CLUSTER_TYPE VARCHAR,
    CHANGE_TYPE VARCHAR NOT NULL,
    SOURCE_VERSION_ID VARCHAR,
    CREATED_AT TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    CREATED_BY VARCHAR,
    COMMENT VARCHAR,
    CONSTRAINT PK_ECL_CLUSTER_VERSIONS PRIMARY KEY (VERSION_ID)
)
COMMENT = 'Append-only history of authored ECL cluster definitions. VERSION_HASH uniquely identifies the snapshot; CONTENT_HASH identifies equivalent definition content.';

REVOKE UPDATE, DELETE, TRUNCATE
    ON TABLE ECL_CLUSTER_VERSIONS
    FROM DATABASE ROLE SC__TERMINOLOGY__WRITER;

REVOKE UPDATE, DELETE, TRUNCATE
    ON TABLE ECL_CLUSTER_VERSIONS
    FROM DATABASE ROLE DB__WRITER;

INSERT INTO ECL_CLUSTER_VERSIONS (
    VERSION_ID,
    VERSION_HASH,
    CONTENT_HASH,
    ECL_EXPRESSION_HASH,
    CLUSTER_UID,
    CLUSTER_ID,
    VERSION_NUMBER,
    ECL_EXPRESSION,
    DESCRIPTION,
    CLUSTER_TYPE,
    CHANGE_TYPE,
    CREATED_AT,
    CREATED_BY,
    COMMENT
)
SELECT
    UUID_STRING() AS VERSION_ID,
    SHA2(
        c.cluster_uid || '|1|' ||
        COALESCE(c.ecl_expression, '') || '|' ||
        COALESCE(c.description, '') || '|' ||
        COALESCE(c.cluster_type, '')
    ) AS VERSION_HASH,
    SHA2(
        COALESCE(c.ecl_expression, '') || '|' ||
        COALESCE(c.description, '') || '|' ||
        COALESCE(c.cluster_type, '')
    ) AS CONTENT_HASH,
    ECL_EXPRESSION_HASH(c.ecl_expression) AS ECL_EXPRESSION_HASH,
    c.cluster_uid,
    c.cluster_id,
    1 AS VERSION_NUMBER,
    c.ecl_expression,
    c.description,
    c.cluster_type,
    'BACKFILL' AS CHANGE_TYPE,
    COALESCE(c.updated_at, c.created_at, CURRENT_TIMESTAMP()) AS CREATED_AT,
    COALESCE(c.updated_by, c.created_by, CURRENT_USER()) AS CREATED_BY,
    'Initial version captured when append-only versioning was enabled' AS COMMENT
FROM ECL_CLUSTERS c
WHERE NOT EXISTS (
    SELECT 1
    FROM ECL_CLUSTER_VERSIONS v
    WHERE v.cluster_uid = c.cluster_uid
);

CREATE OR REPLACE PROCEDURE SAVE_ECL_CLUSTER_VERSION(
    P_CLUSTER_UID VARCHAR,
    P_CLUSTER_ID VARCHAR,
    P_ECL_EXPRESSION VARCHAR,
    P_DESCRIPTION VARCHAR,
    P_CLUSTER_TYPE VARCHAR,
    P_ACTOR VARCHAR,
    P_CHANGE_TYPE VARCHAR,
    P_SOURCE_VERSION_ID VARCHAR,
    P_COMMENT VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    v_actor VARCHAR;
    v_content_hash VARCHAR;
    v_ecl_expression_hash VARCHAR;
    v_latest_content_hash VARCHAR;
    v_version_number NUMBER;
    v_version_id VARCHAR;
    v_version_hash VARCHAR;
BEGIN
    v_actor := IFF(
        p_actor IS NULL OR TRIM(p_actor) = '',
        CURRENT_USER(),
        TRIM(p_actor)
    );
    v_content_hash := SHA2(
        COALESCE(p_ecl_expression, '') || '|' ||
        COALESCE(p_description, '') || '|' ||
        COALESCE(p_cluster_type, '')
    );
    SELECT ECL_EXPRESSION_HASH(:p_ecl_expression)
    INTO v_ecl_expression_hash;

    SELECT MAX_BY(content_hash, version_number), COALESCE(MAX(version_number), 0) + 1
    INTO v_latest_content_hash, v_version_number
    FROM ECL_CLUSTER_VERSIONS
    WHERE cluster_uid = :p_cluster_uid;

    IF (
        v_latest_content_hash = v_content_hash
        AND UPPER(COALESCE(p_change_type, 'UPDATE')) NOT IN ('RESTORE', 'RENAME', 'DELETE')
    ) THEN
        RETURN 'SKIPPED: Definition content unchanged';
    END IF;

    v_version_id := UUID_STRING();
    v_version_hash := SHA2(
        p_cluster_uid || '|' || v_version_number || '|' ||
        v_version_id || '|' || v_content_hash
    );

    INSERT INTO ECL_CLUSTER_VERSIONS (
        version_id,
        version_hash,
        content_hash,
        ecl_expression_hash,
        cluster_uid,
        cluster_id,
        version_number,
        ecl_expression,
        description,
        cluster_type,
        change_type,
        source_version_id,
        created_by,
        comment
    )
    VALUES (
        :v_version_id,
        :v_version_hash,
        :v_content_hash,
        :v_ecl_expression_hash,
        :p_cluster_uid,
        UPPER(TRIM(:p_cluster_id)),
        :v_version_number,
        :p_ecl_expression,
        :p_description,
        :p_cluster_type,
        UPPER(COALESCE(:p_change_type, 'UPDATE')),
        :p_source_version_id,
        :v_actor,
        :p_comment
    );

    RETURN 'SUCCESS: Saved version ' || v_version_number || ' (' || v_version_hash || ')';
END;
$$;

-- =============================================================================
-- Cache refresh procedures
-- =============================================================================

CREATE OR REPLACE PROCEDURE REFRESH_ECL_CLUSTER(
    CLUSTER_ID VARCHAR,
    ACTOR VARCHAR
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'refresh_ecl_cluster'
EXECUTE AS OWNER
AS
$$
from datetime import datetime, timedelta
import time


def sql_escape(value):
    if value is None:
        return ""
    return str(value).replace("'", "''")


def actor_sql(actor):
    escaped = sql_escape(actor).strip()
    return f"'{escaped}'" if escaped else "CURRENT_USER()"


def update_error_metadata(session, cluster_id, error_msg):
    safe_id = sql_escape(cluster_id)
    safe_error = sql_escape(error_msg)
    session.sql(f"""
        MERGE INTO ECL_CACHE_METADATA AS target
        USING (SELECT '{safe_id}' AS cluster_id) AS source
        ON target.cluster_id = source.cluster_id
        WHEN MATCHED THEN
            UPDATE SET last_error_message = '{safe_error}'
        WHEN NOT MATCHED THEN
            INSERT (cluster_id, last_error_message)
            VALUES ('{safe_id}', '{safe_error}')
    """).collect()


def refresh_ecl_cluster(session, cluster_id, actor=None):
    try:
        safe_id = sql_escape(cluster_id)
        cluster_rows = session.sql(f"""
            SELECT
                c.ecl_expression,
                ECL_EXPRESSION_HASH(c.ecl_expression) AS current_hash,
                m.ecl_expression_hash AS stored_hash,
                m.last_successful_refresh
            FROM ECL_CLUSTERS c
            LEFT JOIN ECL_CACHE_METADATA m
              ON c.cluster_id = m.cluster_id
            WHERE c.cluster_id = '{safe_id}'
        """).collect()

        if not cluster_rows:
            return f"ERROR: Cluster {cluster_id} not found in ECL_CLUSTERS"

        row = cluster_rows[0]
        ecl_expression = row["ECL_EXPRESSION"]
        current_hash = row["CURRENT_HASH"]
        stored_hash = row["STORED_HASH"]
        last_refresh = row["LAST_SUCCESSFUL_REFRESH"]

        if not ecl_expression:
            return f"ERROR: Cluster {cluster_id} has no ECL expression"

        needs_refresh = (
            not stored_hash
            or stored_hash != current_hash
            or not last_refresh
        )
        if not needs_refresh:
            refresh_dt = last_refresh
            if hasattr(refresh_dt, "to_pydatetime"):
                refresh_dt = refresh_dt.to_pydatetime()
            if getattr(refresh_dt, "tzinfo", None):
                refresh_dt = refresh_dt.replace(tzinfo=None)
            needs_refresh = refresh_dt < (datetime.utcnow() - timedelta(days=1))

        if not needs_refresh:
            return (
                f"SKIPPED: Cluster {cluster_id} is up to date "
                f"(last refresh: {last_refresh})"
            )

        actor_expr = actor_sql(actor)
        safe_hash = sql_escape(current_hash)
        safe_ecl = sql_escape(ecl_expression)
        refresh_session_id = f"{cluster_id}_{int(time.time() * 1000)}"

        session.sql(f"""
            MERGE INTO ECL_CACHE_METADATA AS target
            USING (SELECT '{safe_id}' AS cluster_id) AS source
            ON target.cluster_id = source.cluster_id
            WHEN MATCHED THEN UPDATE SET
                last_attempted_refresh = CURRENT_TIMESTAMP(),
                last_attempted_by = {actor_expr}
            WHEN NOT MATCHED THEN
                INSERT (
                    cluster_id,
                    last_attempted_refresh,
                    last_attempted_by
                )
                VALUES (
                    '{safe_id}',
                    CURRENT_TIMESTAMP(),
                    {actor_expr}
                )
        """).collect()

        current_rows = session.sql(f"""
            SELECT code, display, system
            FROM ECL_CACHE
            WHERE cluster_id = '{safe_id}'
        """).collect()
        current_codes = {
            row["CODE"]: {
                "display": row["DISPLAY"] or "",
                "system": row["SYSTEM"] or "",
            }
            for row in current_rows
        }
        is_first_refresh = not current_codes

        session.sql("BEGIN TRANSACTION").collect()
        try:
            session.sql(
                f"DELETE FROM ECL_CACHE WHERE cluster_id = '{safe_id}'"
            ).collect()
            session.sql(f"""
                INSERT INTO ECL_CACHE (
                    cluster_id,
                    code,
                    display,
                    system,
                    last_refreshed,
                    ecl_expression_hash
                )
                SELECT
                    '{safe_id}',
                    code,
                    display,
                    system,
                    CURRENT_TIMESTAMP(),
                    '{safe_hash}'
                FROM TABLE(
                    EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS(
                        '{safe_ecl}',
                        'production1'
                    )
                )
            """).collect()

            result_count = session.sql(f"""
                SELECT COUNT(*) AS record_count
                FROM ECL_CACHE
                WHERE cluster_id = '{safe_id}'
            """).collect()[0]["RECORD_COUNT"]

            if result_count == 0:
                session.sql("ROLLBACK").collect()
                error_msg = "Empty result: ECL expression returned no codes"
                update_error_metadata(session, cluster_id, error_msg)
                return f"ERROR: {error_msg}"

            session.sql(f"""
                MERGE INTO ECL_CACHE_METADATA AS target
                USING (SELECT '{safe_id}' AS cluster_id) AS source
                ON target.cluster_id = source.cluster_id
                WHEN MATCHED THEN UPDATE SET
                    last_successful_refresh = CURRENT_TIMESTAMP(),
                    last_attempted_refresh = CURRENT_TIMESTAMP(),
                    last_refreshed_by = {actor_expr},
                    last_attempted_by = {actor_expr},
                    last_error_message = NULL,
                    ecl_expression_hash = '{safe_hash}',
                    record_count = {result_count}
                WHEN NOT MATCHED THEN INSERT (
                    cluster_id,
                    last_successful_refresh,
                    last_attempted_refresh,
                    last_refreshed_by,
                    last_attempted_by,
                    ecl_expression_hash,
                    record_count
                )
                VALUES (
                    '{safe_id}',
                    CURRENT_TIMESTAMP(),
                    CURRENT_TIMESTAMP(),
                    {actor_expr},
                    {actor_expr},
                    '{safe_hash}',
                    {result_count}
                )
            """).collect()

            change_summary = " (initial load - no changes tracked)"
            if not is_first_refresh:
                new_rows = session.sql(f"""
                    SELECT code, display, system
                    FROM ECL_CACHE
                    WHERE cluster_id = '{safe_id}'
                """).collect()
                new_codes = {
                    row["CODE"]: {
                        "display": row["DISPLAY"] or "",
                        "system": row["SYSTEM"] or "",
                    }
                    for row in new_rows
                }
                added_codes = set(new_codes) - set(current_codes)
                removed_codes = set(current_codes) - set(new_codes)

                for code in added_codes:
                    data = new_codes[code]
                    session.sql(f"""
                        INSERT INTO ECL_CLUSTER_CHANGES (
                            cluster_id,
                            change_type,
                            code,
                            display,
                            system,
                            changed_by,
                            refresh_session_id
                        )
                        VALUES (
                            '{safe_id}',
                            'ADDED',
                            '{sql_escape(code)}',
                            '{sql_escape(data["display"])}',
                            '{sql_escape(data["system"])}',
                            {actor_expr},
                            '{sql_escape(refresh_session_id)}'
                        )
                    """).collect()

                for code in removed_codes:
                    data = current_codes[code]
                    session.sql(f"""
                        INSERT INTO ECL_CLUSTER_CHANGES (
                            cluster_id,
                            change_type,
                            code,
                            display,
                            system,
                            changed_by,
                            refresh_session_id
                        )
                        VALUES (
                            '{safe_id}',
                            'REMOVED',
                            '{sql_escape(code)}',
                            '{sql_escape(data["display"])}',
                            '{sql_escape(data["system"])}',
                            {actor_expr},
                            '{sql_escape(refresh_session_id)}'
                        )
                    """).collect()

                change_summary = (
                    f", {len(added_codes)} added, "
                    f"{len(removed_codes)} removed"
                )

            session.sql("COMMIT").collect()
            return (
                f"SUCCESS: Refreshed cluster {cluster_id} with "
                f"{result_count} codes{change_summary}"
            )
        except Exception as cache_error:
            session.sql("ROLLBACK").collect()
            error_msg = f"API Error: {cache_error}"
            update_error_metadata(session, cluster_id, error_msg)
            return f"ERROR: {error_msg}"
    except Exception as error:
        error_msg = f"Exception during refresh: {error}"
        try:
            update_error_metadata(session, cluster_id, error_msg)
        except Exception:
            pass
        return f"ERROR: {error_msg}"
$$;

CREATE OR REPLACE PROCEDURE REFRESH_ECL_CLUSTER(CLUSTER_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'refresh_ecl_cluster_simple'
EXECUTE AS OWNER
AS
$$
def refresh_ecl_cluster_simple(session, cluster_id):
    try:
        return session.call("REFRESH_ECL_CLUSTER", cluster_id, None)
    except Exception as error:
        return f"ERROR: Exception during refresh: {error}"
$$;

CREATE OR REPLACE PROCEDURE FORCE_REFRESH_ECL_CLUSTER(
    CLUSTER_ID VARCHAR,
    ACTOR VARCHAR
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'force_refresh_ecl_cluster'
EXECUTE AS OWNER
AS
$$
def sql_escape(value):
    if value is None:
        return ""
    return str(value).replace("'", "''")


def force_refresh_ecl_cluster(session, cluster_id, actor=None):
    try:
        safe_id = sql_escape(cluster_id)
        session.sql(f"""
            UPDATE ECL_CACHE_METADATA
            SET last_successful_refresh = NULL
            WHERE cluster_id = '{safe_id}'
        """).collect()
        return session.call("REFRESH_ECL_CLUSTER", cluster_id, actor)
    except Exception as error:
        return f"ERROR: Exception during force refresh: {error}"
$$;

CREATE OR REPLACE PROCEDURE FORCE_REFRESH_ECL_CLUSTER(CLUSTER_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'force_refresh_ecl_cluster_simple'
EXECUTE AS OWNER
AS
$$
def force_refresh_ecl_cluster_simple(session, cluster_id):
    try:
        return session.call("FORCE_REFRESH_ECL_CLUSTER", cluster_id, None)
    except Exception as error:
        return f"ERROR: Exception during force refresh: {error}"
$$;

CREATE OR REPLACE PROCEDURE REFRESH_ALL_ECL_CLUSTERS(
    FORCE BOOLEAN,
    ACTOR VARCHAR
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'refresh_all_ecl_clusters'
EXECUTE AS OWNER
AS
$$
def refresh_all_ecl_clusters(session, force=False, actor=None):
    try:
        query = """
            SELECT cluster_id
            FROM ECL_CLUSTERS c
            LEFT JOIN ECL_CACHE_METADATA m USING (cluster_id)
        """
        if not force:
            query += """
                WHERE m.last_successful_refresh IS NULL
                   OR m.last_successful_refresh
                        < DATEADD(day, -1, CURRENT_TIMESTAMP())
                   OR ECL_EXPRESSION_HASH(c.ecl_expression)
                        != COALESCE(m.ecl_expression_hash, '')
            """
        query += " ORDER BY cluster_id"

        clusters = session.sql(query).collect()
        if not clusters:
            return (
                "No clusters found"
                if force
                else "SUCCESS: All clusters are already up to date"
            )

        results = []
        successful = 0
        failed = 0
        for row in clusters:
            cluster_id = row["CLUSTER_ID"]
            if force:
                result = session.call(
                    "FORCE_REFRESH_ECL_CLUSTER",
                    cluster_id,
                    actor,
                )
            else:
                result = session.call(
                    "REFRESH_ECL_CLUSTER",
                    cluster_id,
                    actor,
                )
            results.append(f"- {cluster_id}: {result}")
            if str(result).startswith("SUCCESS"):
                successful += 1
            elif str(result).startswith("ERROR"):
                failed += 1

        skipped = len(clusters) - successful - failed
        results.append(
            f"Summary: {successful} successful, "
            f"{failed} failed, {skipped} skipped"
        )
        return "\n".join(results)
    except Exception as error:
        return f"ERROR: Exception during refresh all clusters: {error}"
$$;

CREATE OR REPLACE PROCEDURE REFRESH_ALL_ECL_CLUSTERS(
    FORCE BOOLEAN DEFAULT FALSE
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'refresh_all_ecl_clusters_compat'
EXECUTE AS OWNER
AS
$$
def refresh_all_ecl_clusters_compat(session, force=False):
    try:
        return session.call("REFRESH_ALL_ECL_CLUSTERS", force, None)
    except Exception as error:
        return f"ERROR: Exception during refresh all clusters: {error}"
$$;

CREATE OR REPLACE PROCEDURE UPSERT_ECL_CLUSTER(
    P_CLUSTER_ID VARCHAR,
    P_ECL_EXPRESSION VARCHAR,
    P_DESCRIPTION VARCHAR,
    P_ACTOR VARCHAR,
    P_CLUSTER_TYPE VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    v_id VARCHAR;
    v_actor VARCHAR;
    v_type VARCHAR;
    v_cluster_uid VARCHAR;
    v_exists NUMBER;
    v_changed BOOLEAN;
    v_change_type VARCHAR;
    v_action VARCHAR;
    v_version_message VARCHAR;
    v_transaction_started BOOLEAN DEFAULT FALSE;
BEGIN
    v_id := UPPER(TRIM(p_cluster_id));
    v_actor := IFF(
        p_actor IS NULL OR TRIM(p_actor) = '',
        CURRENT_USER(),
        TRIM(p_actor)
    );
    v_type := UPPER(COALESCE(NULLIF(TRIM(p_cluster_type), ''), 'OBSERVATION'));
    IF (v_type NOT IN ('OBSERVATION', 'MEDICATION', 'BOTH', 'OTHER')) THEN
        v_type := 'OBSERVATION';
    END IF;

    SELECT COUNT(*)
    INTO v_exists
    FROM ECL_CLUSTERS
    WHERE cluster_id = :v_id;

    BEGIN TRANSACTION;
    v_transaction_started := TRUE;

    IF (v_exists = 0) THEN
        v_cluster_uid := UUID_STRING();
        v_changed := TRUE;
        v_change_type := 'CREATE';
        v_action := 'Created';

        INSERT INTO ECL_CLUSTERS (
            cluster_uid,
            cluster_id,
            ecl_expression,
            description,
            cluster_type,
            created_by,
            updated_by,
            created_at,
            updated_at
        )
        VALUES (
            :v_cluster_uid,
            :v_id,
            :p_ecl_expression,
            :p_description,
            :v_type,
            :v_actor,
            :v_actor,
            CURRENT_TIMESTAMP(),
            CURRENT_TIMESTAMP()
        );
    ELSE
        v_change_type := 'UPDATE';
        v_action := 'Updated';
        SELECT
            cluster_uid,
            NOT (
                EQUAL_NULL(ecl_expression, :p_ecl_expression)
                AND EQUAL_NULL(description, :p_description)
                AND EQUAL_NULL(cluster_type, :v_type)
            )
        INTO v_cluster_uid, v_changed
        FROM ECL_CLUSTERS
        WHERE cluster_id = :v_id;

        IF (v_cluster_uid IS NULL) THEN
            v_cluster_uid := UUID_STRING();
        END IF;

        IF (v_changed) THEN
            UPDATE ECL_CLUSTERS
            SET cluster_uid = :v_cluster_uid,
                ecl_expression = :p_ecl_expression,
                description = :p_description,
                cluster_type = :v_type,
                updated_at = CURRENT_TIMESTAMP(),
                updated_by = :v_actor
            WHERE cluster_id = :v_id;
        END IF;
    END IF;

    IF (v_changed) THEN
        CALL SAVE_ECL_CLUSTER_VERSION(
            :v_cluster_uid,
            :v_id,
            :p_ecl_expression,
            :p_description,
            :v_type,
            :v_actor,
            :v_change_type,
            NULL,
            NULL
        ) INTO v_version_message;

        COMMIT;
        v_transaction_started := FALSE;

        BEGIN
            CALL FORCE_REFRESH_ECL_CLUSTER(:v_id, :v_actor);
        EXCEPTION
            WHEN OTHER THEN
                NULL;
        END;

        RETURN 'SUCCESS: ' || v_action || ' ' || v_id || '; ' ||
            v_version_message;
    END IF;

    COMMIT;
    v_transaction_started := FALSE;
    RETURN 'SKIPPED: Definition unchanged for ' || v_id;
EXCEPTION
    WHEN OTHER THEN
        IF (v_transaction_started) THEN
            ROLLBACK;
        END IF;
        RETURN 'ERROR: ' || SQLERRM;
END;
$$;

CREATE OR REPLACE PROCEDURE RESTORE_ECL_CLUSTER_VERSION(
    P_CLUSTER_ID VARCHAR,
    P_VERSION_ID VARCHAR,
    P_ACTOR VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    v_id VARCHAR;
    v_actor VARCHAR;
    v_cluster_uid VARCHAR;
    v_ecl_expression VARCHAR;
    v_description VARCHAR;
    v_cluster_type VARCHAR;
    v_version_number NUMBER;
    v_version_message VARCHAR;
    v_comment VARCHAR;
    v_transaction_started BOOLEAN DEFAULT FALSE;
BEGIN
    v_id := UPPER(TRIM(p_cluster_id));
    v_actor := IFF(
        p_actor IS NULL OR TRIM(p_actor) = '',
        CURRENT_USER(),
        TRIM(p_actor)
    );

    SELECT c.cluster_uid
    INTO v_cluster_uid
    FROM ECL_CLUSTERS c
    WHERE c.cluster_id = :v_id;

    SELECT
        ecl_expression,
        description,
        cluster_type,
        version_number
    INTO
        v_ecl_expression,
        v_description,
        v_cluster_type,
        v_version_number
    FROM ECL_CLUSTER_VERSIONS
    WHERE version_id = :p_version_id
      AND cluster_uid = :v_cluster_uid;

    v_comment := 'Restored from version ' || v_version_number;

    BEGIN TRANSACTION;
    v_transaction_started := TRUE;

    UPDATE ECL_CLUSTERS
    SET ecl_expression = :v_ecl_expression,
        description = :v_description,
        cluster_type = :v_cluster_type,
        updated_at = CURRENT_TIMESTAMP(),
        updated_by = :v_actor
    WHERE cluster_id = :v_id;

    CALL SAVE_ECL_CLUSTER_VERSION(
        :v_cluster_uid,
        :v_id,
        :v_ecl_expression,
        :v_description,
        :v_cluster_type,
        :v_actor,
        'RESTORE',
        :p_version_id,
        :v_comment
    ) INTO v_version_message;

    COMMIT;
    v_transaction_started := FALSE;

    BEGIN
        CALL FORCE_REFRESH_ECL_CLUSTER(:v_id, :v_actor);
    EXCEPTION
        WHEN OTHER THEN
            NULL;
    END;

    RETURN 'SUCCESS: Restored ' || v_id || ' from version ' ||
        v_version_number || '; ' || v_version_message;
EXCEPTION
    WHEN OTHER THEN
        IF (v_transaction_started) THEN
            ROLLBACK;
        END IF;
        RETURN 'ERROR: Restore failed: ' || SQLERRM;
END;
$$;

CREATE OR REPLACE PROCEDURE RENAME_ECL_CLUSTER(
    P_OLD_CLUSTER_ID VARCHAR,
    P_NEW_CLUSTER_ID VARCHAR,
    P_ECL_EXPRESSION VARCHAR,
    P_DESCRIPTION VARCHAR,
    P_ACTOR VARCHAR,
    P_CLUSTER_TYPE VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    v_old VARCHAR;
    v_new VARCHAR;
    v_exists NUMBER;
    v_actor VARCHAR;
    v_type VARCHAR;
    v_cluster_uid VARCHAR;
    v_version_message VARCHAR;
    v_comment VARCHAR;
    v_transaction_started BOOLEAN DEFAULT FALSE;
BEGIN
    v_old := TRIM(p_old_cluster_id);
    v_new := UPPER(TRIM(p_new_cluster_id));
    v_actor := IFF(
        p_actor IS NULL OR TRIM(p_actor) = '',
        CURRENT_USER(),
        TRIM(p_actor)
    );
    v_type := UPPER(COALESCE(NULLIF(TRIM(p_cluster_type), ''), 'OBSERVATION'));
    IF (v_type NOT IN ('OBSERVATION', 'MEDICATION', 'BOTH', 'OTHER')) THEN
        v_type := 'OBSERVATION';
    END IF;

    SELECT cluster_uid
    INTO v_cluster_uid
    FROM ECL_CLUSTERS
    WHERE cluster_id = :v_old;

    IF (UPPER(v_old) != v_new) THEN
        SELECT COUNT(*)
        INTO v_exists
        FROM ECL_CLUSTERS
        WHERE cluster_id = :v_new;

        IF (v_exists > 0) THEN
            RETURN 'ERROR: Target cluster already exists: ' || v_new;
        END IF;
    END IF;

    BEGIN TRANSACTION;
    v_transaction_started := TRUE;

    UPDATE ECL_CLUSTERS
    SET cluster_id = :v_new,
        ecl_expression = :p_ecl_expression,
        description = :p_description,
        cluster_type = :v_type,
        updated_at = CURRENT_TIMESTAMP(),
        updated_by = :v_actor
    WHERE cluster_id = :v_old;

    IF (UPPER(v_old) != v_new) THEN
        UPDATE ECL_CACHE SET cluster_id = :v_new WHERE cluster_id = :v_old;
        UPDATE ECL_CACHE_METADATA SET cluster_id = :v_new WHERE cluster_id = :v_old;
    END IF;

    v_comment := 'Renamed from ' || v_old || ' to ' || v_new;

    CALL SAVE_ECL_CLUSTER_VERSION(
        :v_cluster_uid,
        :v_new,
        :p_ecl_expression,
        :p_description,
        :v_type,
        :v_actor,
        'RENAME',
        NULL,
        :v_comment
    ) INTO v_version_message;

    COMMIT;
    v_transaction_started := FALSE;

    BEGIN
        CALL FORCE_REFRESH_ECL_CLUSTER(:v_new, :v_actor);
    EXCEPTION
        WHEN OTHER THEN
            NULL;
    END;

    RETURN 'SUCCESS: Renamed ' || v_old || ' to ' || v_new || '; ' ||
        v_version_message;
EXCEPTION
    WHEN OTHER THEN
        IF (v_transaction_started) THEN
            ROLLBACK;
        END IF;
        RETURN 'ERROR: Rename failed: ' || SQLERRM;
END;
$$;

CREATE OR REPLACE PROCEDURE DELETE_ECL_CLUSTER(P_CLUSTER_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    v_id VARCHAR;
    v_cluster_uid VARCHAR;
    v_ecl_expression VARCHAR;
    v_description VARCHAR;
    v_cluster_type VARCHAR;
    v_version_message VARCHAR;
    v_transaction_started BOOLEAN DEFAULT FALSE;
BEGIN
    v_id := TRIM(p_cluster_id);

    SELECT cluster_uid, ecl_expression, description, cluster_type
    INTO v_cluster_uid, v_ecl_expression, v_description, v_cluster_type
    FROM ECL_CLUSTERS
    WHERE cluster_id = :v_id;

    BEGIN TRANSACTION;
    v_transaction_started := TRUE;

    CALL SAVE_ECL_CLUSTER_VERSION(
        :v_cluster_uid,
        :v_id,
        :v_ecl_expression,
        :v_description,
        :v_cluster_type,
        CURRENT_USER(),
        'DELETE',
        NULL,
        'Cluster deleted; definition history retained'
    ) INTO v_version_message;

    DELETE FROM ECL_CACHE WHERE cluster_id = :v_id;
    DELETE FROM ECL_CACHE_METADATA WHERE cluster_id = :v_id;
    DELETE FROM ECL_CLUSTERS WHERE cluster_id = :v_id;

    COMMIT;
    v_transaction_started := FALSE;

    RETURN 'SUCCESS: Deleted ' || v_id || '; ' || v_version_message;
EXCEPTION
    WHEN OTHER THEN
        IF (v_transaction_started) THEN
            ROLLBACK;
        END IF;
        RETURN 'ERROR: ' || SQLERRM;
END;
$$;
