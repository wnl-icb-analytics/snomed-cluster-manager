/*
================================================================================
SNOMED Cluster Manager weekly refresh
================================================================================
Refreshes every ECL cluster on Sundays at 02:00 UTC.
================================================================================
*/

USE ROLE DATA_PLATFORM_MANAGER;
USE SCHEMA APPLICATIONS.SNOMED_CLUSTER_MANAGER;

CREATE OR REPLACE TASK ECL_CACHE_REFRESH_TASK
    WAREHOUSE = WH_NCL_ENGINEERING_XS
    SCHEDULE = 'USING CRON 0 2 * * 0 UTC'
    COMMENT = 'Weekly refresh of all ECL cached clusters'
AS
    CALL APPLICATIONS.SNOMED_CLUSTER_MANAGER.REFRESH_ALL_ECL_CLUSTERS();

ALTER TASK ECL_CACHE_REFRESH_TASK RESUME;
