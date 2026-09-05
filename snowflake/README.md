# Snowflake pipeline — load → dbt → export

This rebuilds the prospect marts from raw Shodan scan data. It needs Snowflake credentials
and a Python env with `snowflake-connector-python` + `dbt-snowflake` — **both install and
run on Python 3.14** (verified), so the app's own `backend/.venv` works; the repo also has
a 3.12 `.venv-snow` from earlier and either is fine. The committed `data/marts/*.json`
snapshot means you only need this if you're re-loading data or changing the transforms.

## Layout
```
snowflake/
  loader/load_raw.py        PUT a local NDJSON file into a stage, COPY INTO RAW.SCANS(v VARIANT)
  dbt_firmable/             dbt project: staging (view) → intermediate (view) → marts (table)
    models/staging/         stg_services            typed 1-row-per-service, honeypots dropped
    models/intermediate/    int_service_signals     per-service security findings (deterministic)
                            int_service_company     entity resolution → company_domain
    models/marts/           dim_company, fct_account_score
    seeds/infra_domains.csv hosting/CDN domains excluded from entity resolution
```

## Prerequisites
- A Python env with `snowflake-connector-python` and `dbt-snowflake` — **3.14 or 3.12 both
  work** (e.g. the app's `backend/.venv`, or the repo's `.venv-snow`; commands below use
  `.venv-snow`, swap the path for whichever you use).
- `.env` at the repo root with the `SNOWFLAKE_*` values and a key-pair (`.p8`) whose public
  key is registered on the Snowflake user. See `backend/.env.example` for the variable list.
- Key-pair auth (not password + MFA) so the loader and dbt run headless. `load_raw.py` reads
  `SNOWFLAKE_PRIVATE_KEY_PATH` (repo-relative); dbt's `profiles.yml` reads
  `SNOWFLAKE_PRIVATE_KEY_PATH_ABS` (absolute).

## 1. Load raw scans
```bash
./.venv-snow/bin/python snowflake/loader/load_raw.py data/raw/shodan_sample_1k.jsonl --truncate
```
Creates `FIRMABLE.RAW.SCANS(v VARIANT)` plus the file format and stage if absent, PUTs the
file (auto-gzip) to the internal stage, and `COPY INTO`s it. `--truncate` reloads from
scratch. For the full 74 GB file, point at an external stage (S3) + Snowpipe and scale the
warehouse instead of a single PUT — see `docs/improvements.md` #9.

## 2. Build the marts with dbt
```bash
cd snowflake/dbt_firmable
export SNOWFLAKE_PRIVATE_KEY_PATH_ABS="$(cd ../.. && pwd)/.secrets/snowflake_rsa_key.p8"
../../.venv-snow/bin/dbt deps          # first run only
../../.venv-snow/bin/dbt seed          # loads infra_domains.csv
../../.venv-snow/bin/dbt build         # runs models + tests (not-null / unique / accepted-values)
```
`dbt build` runs the models and their tests together. Staging/intermediate materialise as
views (free, always fresh); the marts materialise as tables. Schemas land as
`FIRMABLE.DBT_STAGING`, `DBT_INTERMEDIATE`, `DBT_MARTS`, `DBT_SEEDS`.

## 3. Publish the snapshot the app serves
```bash
cd backend
PYTHONPATH=. ../.venv-snow/bin/python -m app.export_marts     # add --limit-services N to cap
```
Writes `data/marts/companies.json` and `services.json` — the snapshot the default
`DATA_BACKEND=local` API reads. Commit these to refresh the demo.

To skip the snapshot and have the API query the marts live, set `DATA_BACKEND=snowflake`
(needs credentials and the 3.12 environment at runtime) — do this once the full-scale marts
are too large to snapshot locally.

## Full load via S3 external stage (74 GB)

The sample loads via the internal stage above. The full ~13 GB compressed / ~74 GB
uncompressed export is loaded from **S3 in `ap-southeast-1`** (this account's region — same
region ⇒ no data-transfer cost) via an external stage. Files:
`loader/split_ndjson.py` (splitter) and `loader/load_full_s3.sql` (the Snowflake side).

**1. Split into parallel-friendly chunks.** COPY parallelises ~one file per warehouse
thread, so one 13 GB file loads on one thread. Split into many ~150 MB gzip parts:
```bash
./.venv-snow/bin/python snowflake/loader/split_ndjson.py <full.ndjson> ./chunks
# .zst source: zstd -dc full.ndjson.zst | ./.venv-snow/bin/python snowflake/loader/split_ndjson.py - ./chunks
```

**2. Bucket in ap-southeast-1 + upload** (S3 ingress and in-region S3→Snowflake are free):
```bash
aws s3 mb s3://<BUCKET> --region ap-southeast-1
aws s3 cp ./chunks/ s3://<BUCKET>/scans/ --recursive
```

**3. Storage integration + IAM handshake.** Run steps 1–2 of `loader/load_full_s3.sql`
(as ACCOUNTADMIN); `desc integration S3_SHODAN` prints `STORAGE_AWS_IAM_USER_ARN` and
`STORAGE_AWS_EXTERNAL_ID`. Create an IAM role `snowflake-shodan-load` with:

*Trust policy* (who may assume it):
```json
{ "Version": "2012-10-17", "Statement": [{
  "Effect": "Allow",
  "Principal": { "AWS": "<STORAGE_AWS_IAM_USER_ARN>" },
  "Action": "sts:AssumeRole",
  "Condition": { "StringEquals": { "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID>" } } }] }
```
*Permission policy* (read the bucket prefix):
```json
{ "Version": "2012-10-17", "Statement": [
  { "Effect": "Allow", "Action": ["s3:GetObject","s3:GetObjectVersion"],
    "Resource": "arn:aws:s3:::<BUCKET>/scans/*" },
  { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::<BUCKET>",
    "Condition": { "StringLike": { "s3:prefix": ["scans/*"] } } } ] }
```
Put this role's ARN in the integration's `storage_aws_role_arn` (already referenced in the
SQL). Using an integration keeps AWS keys out of SQL — the "senior" pattern, and Snowpipe
can reuse the same stage later for continuous loads.

**4. Stage + COPY.** Run steps 4–7 of `load_full_s3.sql`: it defines `EXT_SCANS`, spins up
an auto-suspending `LOAD_WH` (MEDIUM = 32 threads), and `COPY INTO RAW.SCANS`. COPY tracks
loaded files, so re-running after an interruption resumes rather than duplicates.

**5. Rebuild the marts over the full data:**
```bash
cd snowflake/dbt_firmable
export SNOWFLAKE_PRIVATE_KEY_PATH_ABS="$(cd ../.. && pwd)/.secrets/snowflake_rsa_key.p8"
../../.venv-snow/bin/dbt build --full-refresh
```
The entity-resolution `LATERAL FLATTEN` + waterfall over ~10M rows is the heavy step; run
dbt on a MEDIUM warehouse (point `profiles.yml` at `LOAD_WH`, or resize `COMPUTE_WH`). No
redeploy needed — the app (`DATA_BACKEND=snowflake`) serves the full data once dbt finishes.

**Cost (ap-southeast-1):** S3 ingress + in-region transfer $0; S3 storage ~$0.30/mo (delete
`s3://<BUCKET>/scans/` after loading); Snowflake load ~1–3 credits (≈$0 on the trial);
loaded storage ~$2–3/mo (drop `RAW.SCANS` to reclaim). Live app queries scan the full marts
per request — keep the public demo on `DATA_BACKEND=local` if it will get real traffic.

## Notes
- **ELT, not ETL**: the raw JSON lands untouched in `VARIANT` and all transformation happens
  in-warehouse, so re-processing never requires re-loading.
- **Column dictionary** for every layer (raw vs derived) is in `docs/data_model.md`.
- **Honeypot filter**: `stg_services` drops honeypots null-safely
  (`COALESCE(array_contains('honeypot', tags), false)`) — a plain `NOT array_contains(...)`
  drops every untagged row via SQL three-valued logic.
