/*
================================================================================
SNOMED Cluster Manager functions
================================================================================
ECL helper functions. Owned by ENGINEER, which holds usage on
EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS. Readers get usage through the schema reader role.
Run after 01_tables.sql: SQL functions resolve unqualified tables against the
current schema when created.
================================================================================
*/

USE ROLE ENGINEER;
USE SCHEMA APPLICATIONS.SNOMED_CLUSTER_MANAGER;

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.BUILD_UK_MED_PRODUCT_ECL("INGREDIENT_CODES" ARRAY)
RETURNS VARCHAR
LANGUAGE SQL
AS '
  WITH normalized_codes AS (
    SELECT DISTINCT TRIM(value::STRING) AS code
    FROM TABLE(FLATTEN(input => ingredient_codes))
    WHERE value IS NOT NULL
      AND TRIM(value::STRING) <> ''''
  ),
  ingredient_predicates AS (
    SELECT LISTAGG(
      ''(<< 373873005 |Pharmaceutical / biologic product| : 127489000 |Has active ingredient| = << '' || code || '')'',
      '' OR ''
    ) WITHIN GROUP (ORDER BY code) AS predicate_sql
    FROM normalized_codes
  )
  SELECT CASE
    WHEN predicate_sql IS NULL OR predicate_sql = '''' THEN NULL
    ELSE
      ''('' ||
        ''(<< ('' || predicate_sql || ''))'' ||
        '' OR '' ||
        ''(<< 8653601000001108 |Virtual medicinal product pack (product)| : 774160008 |Contains clinical drug| = << ('' || predicate_sql || ''))'' ||
        '' OR '' ||
        ''(<< 10364001000001104 |Actual medicinal product pack (product)| : 10362701000001108 |Has AMP| = << ('' || predicate_sql || ''))'' ||
      '')''
  END
  FROM ingredient_predicates
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.BUILD_UK_MED_PRODUCT_ECL("INGREDIENT_CODES_CSV" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS '
  SELECT APPLICATIONS.SNOMED_CLUSTER_MANAGER.BUILD_UK_MED_PRODUCT_ECL(
    SPLIT(REGEXP_REPLACE(COALESCE(ingredient_codes_csv, ''''), ''\\\\s+'', ''''), '','')
  )
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.ECL_CACHED_DETAILS("CLUSTER_ID" VARCHAR)
RETURNS TABLE ("CODE" VARCHAR, "DISPLAY" VARCHAR, "SYSTEM" VARCHAR, "LAST_REFRESHED" TIMESTAMP_NTZ(9))
LANGUAGE SQL
AS '
    SELECT code, display, system, last_refreshed
    FROM ECL_CACHE
    WHERE cluster_id = $1
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.ECL_EXPRESSION_HASH("ECL_EXPRESSION" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS '
    SELECT SHA2(
        UPPER(
            TRIM(
                REPLACE(
                    REPLACE(ecl_expression, CHR(10), '' ''),
                    CHR(13),
                    '' ''
                )
            )
        ),
        256
    )
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.ECL_TEST_DETAILS("ECL_EXPRESSION" VARCHAR)
RETURNS TABLE ("CODE" VARCHAR, "DISPLAY" VARCHAR, "SYSTEM" VARCHAR)
LANGUAGE SQL
AS '
    SELECT code, display, system
    FROM TABLE(
        EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS(ecl_expression, ''production1'')
    )
    LIMIT 50000
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.UK_MED_PRODUCT_DETAILS("INGREDIENT_CODES" ARRAY)
RETURNS TABLE ("CODE" VARCHAR, "DISPLAY" VARCHAR, "SYSTEM" VARCHAR)
LANGUAGE SQL
AS '
  SELECT code, display, system
  FROM TABLE(
    EXTERNAL_ACCESS.ONTOSERVER.ECL_DETAILS(
      BUILD_UK_MED_PRODUCT_ECL(ingredient_codes),
      ''production1''
    )
  )
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.UK_MED_PRODUCT_DETAILS("INGREDIENT_CODES_CSV" VARCHAR)
RETURNS TABLE ("CODE" VARCHAR, "DISPLAY" VARCHAR, "SYSTEM" VARCHAR)
LANGUAGE SQL
AS '
  SELECT code, display, system
  FROM TABLE(
    APPLICATIONS.SNOMED_CLUSTER_MANAGER.UK_MED_PRODUCT_DETAILS(
      SPLIT(REGEXP_REPLACE(COALESCE(ingredient_codes_csv, ''''), ''\\\\s+'', ''''), '','')
    )
  )
';

CREATE OR REPLACE FUNCTION APPLICATIONS.SNOMED_CLUSTER_MANAGER.ECL_CACHED_CODES("CLUSTER_ID" VARCHAR)
RETURNS TABLE ("CODE" VARCHAR)
LANGUAGE SQL
AS '
    SELECT code
    FROM ECL_CACHE
    WHERE cluster_id = $1
';
