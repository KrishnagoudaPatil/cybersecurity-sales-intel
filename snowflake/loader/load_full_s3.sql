-- Full-scale load: Shodan NDJSON in S3  ->  FIRMABLE.RAW.SCANS (VARIANT)
-- via an external stage backed by an IAM storage integration (no keys in SQL).
--
-- Prereqs handled elsewhere (see snowflake/README.md "Full load via S3 external stage"):
--   * chunks uploaded to s3://<BUCKET>/scans/  (bucket in ap-southeast-1, same as this account)
--   * you can run the ACCOUNTADMIN statements below (storage integrations need it)
--
-- Replace <BUCKET> and <AWS_ACCOUNT_ID> before running.

-- 0. Base objects (idempotent; also created by load_raw.py). RAW.SCANS + JSON file format.
create database if not exists FIRMABLE;
create schema   if not exists FIRMABLE.RAW;
create table    if not exists FIRMABLE.RAW.SCANS (v variant);
create file format if not exists FIRMABLE.RAW.FF_NDJSON type = json strip_outer_array = false;

-- 1. Storage integration (run as ACCOUNTADMIN). The role ARN is the one you create in AWS
--    in step 3; it does not need to exist yet at creation time.
use role ACCOUNTADMIN;
create storage integration if not exists S3_SHODAN
  type = external_stage
  storage_provider = 'S3'
  enabled = true
  storage_aws_role_arn = 'arn:aws:iam::<AWS_ACCOUNT_ID>:role/snowflake-shodan-load'
  storage_allowed_locations = ('s3://<BUCKET>/scans/');

-- 2. Read back the principal + external id that AWS must trust, then build the IAM role
--    (step 3 in the README) with exactly these two values.
desc integration S3_SHODAN;
--    -> copy STORAGE_AWS_IAM_USER_ARN  and  STORAGE_AWS_EXTERNAL_ID from the output.

-- 3. (in AWS) create role 'snowflake-shodan-load' — see README for the trust + read policy.

-- 4. Let SYSADMIN use the integration, then define the external stage (no credentials in SQL).
grant usage on integration S3_SHODAN to role SYSADMIN;
use role SYSADMIN;
create or replace stage FIRMABLE.RAW.EXT_SCANS
  storage_integration = S3_SHODAN
  url = 's3://<BUCKET>/scans/'
  file_format = FIRMABLE.RAW.FF_NDJSON;

-- Sanity check: the stage can see the chunks.
list @FIRMABLE.RAW.EXT_SCANS;

-- 5. Dedicated load warehouse: scaled for parallelism, auto-suspends so idle costs nothing.
create warehouse if not exists LOAD_WH
  warehouse_size = 'MEDIUM'          -- 32 threads; drop to SMALL to halve credits/hour
  auto_suspend = 60 auto_resume = true initially_suspended = true;
use warehouse LOAD_WH;

-- 6. Load. COPY records which files it has already ingested, so re-running after an
--    interruption resumes rather than duplicating. on_error=continue skips bad rows.
copy into FIRMABLE.RAW.SCANS
  from @FIRMABLE.RAW.EXT_SCANS
  file_format = FIRMABLE.RAW.FF_NDJSON
  on_error = 'continue';

-- 7. Verify, then let the warehouse suspend on its own.
select count(*) as raw_rows from FIRMABLE.RAW.SCANS;

-- Next: rebuild the marts over the full data with `dbt build` (see README), after which the
-- deployed app (DATA_BACKEND=snowflake) serves the full dataset with no redeploy.
