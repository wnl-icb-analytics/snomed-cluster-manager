/*
================================================================================
SNOMED Cluster Manager Streamlit app
================================================================================
Git-backed Streamlit in the app schema. The container runtime installs the
dependencies in pyproject.toml from the shared PyPI repository. ENGINEER owns the app, which runs with
owner's rights. Analysts open it through the schema APP_USER role (Snowflake-
Deployment access tables); they cannot call the procedures directly.

The git repository is owned by the schema owner role, as the access model
expects for stage-type objects. FETCH uses the calling user's GitHub sign-in
(Snowflake GitHub App); if it fails with a refresh-token error, sign in again
from Snowsight (Projects > Workspaces > From Git repository > OAuth2).

Deploy a merged change:
    ALTER GIT REPOSITORY APPLICATIONS.SNOMED_CLUSTER_MANAGER."snomed-cluster-manager" FETCH;
    ALTER STREAMLIT APPLICATIONS.SNOMED_CLUSTER_MANAGER.SNOMED_CLUSTER_MANAGER ABORT;
    ALTER STREAMLIT APPLICATIONS.SNOMED_CLUSTER_MANAGER.SNOMED_CLUSTER_MANAGER PULL;
    ALTER STREAMLIT APPLICATIONS.SNOMED_CLUSTER_MANAGER.SNOMED_CLUSTER_MANAGER COMMIT;
    ALTER STREAMLIT APPLICATIONS.SNOMED_CLUSTER_MANAGER.SNOMED_CLUSTER_MANAGER ADD LIVE VERSION FROM LAST;
COMMIT removes the live version, so the last step is needed before analysts can open the app.
If PULL reports the version is already up to date, skip COMMIT and run ADD LIVE VERSION FROM LAST:
ABORT has already removed the live version.
================================================================================
*/

USE ROLE ENGINEER;
USE SCHEMA APPLICATIONS.SNOMED_CLUSTER_MANAGER;

CREATE GIT REPOSITORY IF NOT EXISTS "snomed-cluster-manager"
    API_INTEGRATION = API__GITHUB__WNL_ICB_ANALYTICS
    ORIGIN = 'https://github.com/wnl-icb-analytics/snomed-cluster-manager'
    COMMENT = 'Source for the SNOMED Cluster Manager Streamlit app';

ALTER GIT REPOSITORY "snomed-cluster-manager" FETCH;

GRANT OWNERSHIP ON GIT REPOSITORY "snomed-cluster-manager"
    TO DATABASE ROLE APPLICATIONS.SC__SNOMED_CLUSTER_MANAGER__OWNER COPY CURRENT GRANTS;

CREATE STREAMLIT IF NOT EXISTS SNOMED_CLUSTER_MANAGER
    FROM '@APPLICATIONS.SNOMED_CLUSTER_MANAGER."snomed-cluster-manager"/branches/main/'
    MAIN_FILE = 'streamlit_app.py'
    RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11'
    COMPUTE_POOL = SYSTEM_COMPUTE_POOL_CPU
    QUERY_WAREHOUSE = 'NCL_ANALYTICS_XS'
    TITLE = 'SNOMED Cluster Manager'
    ARTIFACT_REPOSITORIES = (snowflake.snowpark.pypi_shared_repository)
    COMMENT = 'Create, version and refresh ECL-defined SNOMED clusters';

ALTER STREAMLIT SNOMED_CLUSTER_MANAGER ADD LIVE VERSION FROM LAST;
