# Data Model & Column Dictionary

How the raw Shodan scan data flows through Snowflake + dbt, and what every column
means. Columns are marked **[raw]** (extracted straight from the source JSON) or
**[derived]** (computed by a model).

## Pipeline layers

| Layer | Object | Type | Grain | Rows (1k sample) |
|-------|--------|------|-------|------------------|
| Landing | `RAW.SCANS` | table | 1 row per scanned service (raw JSON) | 1,000 |
| Seed | `DBT_SEEDS.INFRA_DOMAINS` | table | 1 row per hosting/CDN domain | 32 |
| Staging | `DBT_STAGING.STG_SERVICES` | view | 1 row per service (typed) | 998 |
| Intermediate | `DBT_INTERMEDIATE.INT_SERVICE_SIGNALS` | view | 1 row per service + findings | 998 |
| Intermediate | `DBT_INTERMEDIATE.INT_SERVICE_COMPANY` | view | 1 row per attributable service | 462 |
| Mart | `DBT_MARTS.DIM_COMPANY` | table | 1 row per company | 157 |
| Mart | `DBT_MARTS.FCT_ACCOUNT_SCORE` | table | 1 row per scored company | 157 |

Data source: Shodan internet-wide scan export — **NDJSON**, one JSON object per line,
~13 GB zstd-compressed / ~74 GB uncompressed (~10M records). Each record is one
service observed on one IP:port.

---

## RAW.SCANS
Single column, semi-structured landing zone.

| Column | Type | Meaning |
|--------|------|---------|
| `v` | VARIANT | The entire raw Shodan JSON record, loaded as-is (ELT: transform later). |

---

## STG_SERVICES — cleaned, typed, one row per service
Light 1:1 cleanup of the VARIANT. Honeypots dropped (`tags` contains `honeypot`,
null-safe via `COALESCE`).

| Column | Source | Kind | Type | Meaning |
|--------|--------|------|------|---------|
| `ip` | `ip_str` / `ipv6` | [derived] | string | Host IP; coalesces IPv4 or IPv6. |
| `is_ipv6` | `ipv6 is not null` | [derived] | bool | True if reached over IPv6. |
| `port` | `port` | [raw] | int | Port the service listens on. |
| `transport` | `transport` | [raw] | string | tcp / udp. |
| `asn` | `asn` | [raw] | string | Autonomous System Number (routing network id). |
| `org` | `org` | [raw] | string | Org owning the IP block — usually the hosting provider. |
| `isp` | `isp` | [raw] | string | Internet service provider (often == org). |
| `scan_module` | `_shodan.module` | [raw] | string | Shodan crawler/module (https, http, ntp, auto…). |
| `observed_at` | `timestamp` | [raw] | timestamp_ntz | When Shodan scanned the service (UTC, no tz). |
| `country_code` | `location.country_code` | [raw] | string | ISO-2 country of the IP. |
| `country_name` | `location.country_name` | [raw] | string | Country name. |
| `city` | `location.city` | [raw] | string | City (IP geolocation, approximate). |
| `domains` | `domains` | [raw] | array | Registrable domains resolving to the IP — entity-resolution input. |
| `hostnames` | `hostnames` | [raw] | array | Full FQDNs / reverse-DNS names. |
| `tags` | `tags` | [raw] | array | Shodan labels: cloud, cdn, self-signed, eol-product, vpn, database, honeypot… |
| `product` | `product` | [raw] | string | Fingerprinted software (e.g. nginx, OpenSSH). |
| `version` | `version` | [raw] | string | Software version if detected. |
| `cpe23` | `cpe23` | [raw] | array | CPE 2.3 software identifiers (map to CVEs). |
| `http_status` | `http.status` | [raw] | int | HTTP response code; NULL means not an HTTP service. |
| `http_headers` | `http.headers` | [raw] | object | HTTP response headers (drives header hygiene checks). |
| `http_title` | `http.title` | [raw] | string | Page title. |
| `has_tls` | `ssl is not null` | [derived] | bool | Whether TLS/SSL (a cert) was observed. |
| `tls_versions` | `ssl.versions` | [raw] | array | TLS/SSL versions offered (legacy = weak). |
| `cert_expired` | `ssl.cert.expired` | [raw] | bool | Whether the TLS cert is expired. |
| `vulns_obj` | `vulns` | [raw] | object | Known CVEs (object keys are CVE ids). |
| `opts_vulns` | `opts.vulns` | [raw] | array | Secondary CVE list (Shodan stores CVEs in two places). |
| `banner` | `data` | [raw] | string | Raw captured response/banner (free text). |
| `raw` | whole record | [raw] | VARIANT | Full original JSON, kept for reprocessing without reload. |

---

## INT_SERVICE_SIGNALS — per-service security findings [all derived]
Adds findings; grain unchanged (1 row per service). The deterministic "rules" layer.

| Column | Derived from | Type | Meaning |
|--------|--------------|------|---------|
| `cve_ids` | `vulns_obj` keys + `opts_vulns`, de-duped | array | Distinct known CVE ids. |
| `cve_count` | `array_size(cve_ids)` | int | Number of known CVEs. |
| `has_known_cve` | `cve_count > 0` | bool | Any known vulnerability present. |
| `is_eol` | `tags` has eol-product | bool | Runs end-of-life software. |
| `is_self_signed` | `tags` has self-signed | bool | Self-signed TLS certificate. |
| `is_vpn` | `tags` has vpn | bool | VPN endpoint. |
| `is_iot` | `tags` has iot | bool | IoT device. |
| `exposed_database` | database tag / known DB port / product match | bool | A database exposed to the internet. |
| `exposed_remote_access` | port in {3389,23,5900,21} | bool | RDP/telnet/VNC/FTP exposed. |
| `has_tls` | carried from staging | bool | TLS observed. |
| `weak_tls` | `tls_versions` has TLSv1/1.1/SSLv3/SSLv2 | bool | Legacy/weak protocol offered. |
| `cert_expired` | `coalesce(cert_expired,false)` | bool | Expired certificate. |
| `is_http` | `http_status is not null` | bool | Is an HTTP service. |
| `missing_hsts` | header absent (http only) | int 0/1 | Missing Strict-Transport-Security. |
| `missing_csp` | header absent (http only) | int 0/1 | Missing Content-Security-Policy. |
| `missing_xfo` | header absent (http only) | int 0/1 | Missing X-Frame-Options. |
| `missing_xcto` | header absent (http only) | int 0/1 | Missing X-Content-Type-Options. |

---

## INT_SERVICE_COMPANY — entity resolution [derived]
Explodes `domains`, drops infra domains (seed anti-join), picks one primary domain per
service. Carries all signal columns through, adds `company_domain`. Services with no
attributable domain drop out.

| Column | Derived from | Meaning |
|--------|--------------|---------|
| `company_domain` | shortest surviving non-infra domain | The company key. |
| *(all INT_SERVICE_SIGNALS finding columns)* | carried through | Per-service findings, now tagged with a company. |

---

## DIM_COMPANY — company dimension [derived, grain = company]

| Column | Meaning |
|--------|---------|
| `company_domain` | Primary registrable domain — the company key. |
| `host_count` | Distinct IPs attributed to the company. |
| `service_count` | Distinct services (IP:port). |
| `distinct_ports` | Distinct ports exposed. |
| `primary_country` | Most common country of the company's hosts. |
| `primary_hosting_org` | Most common org (hosting provider). |
| `last_seen` | Most recent scan timestamp. |
| `size_band` | micro/small/mid/enterprise from host_count. |

---

## FCT_ACCOUNT_SCORE — scored prospects [derived, grain = company]

| Column | Meaning |
|--------|---------|
| `company_domain` | Company key. |
| `host_count`, `service_count`, `primary_country` | Footprint context. |
| `total_cves` | Sum of CVEs across the company's services. |
| `services_with_cve` | Count of services with >=1 CVE. |
| `exposed_db_services` | Count of exposed databases. |
| `exposed_remote_services` | Count of exposed RDP/telnet/VNC/FTP. |
| `eol_services` | Count running end-of-life software. |
| `self_signed_services` | Count with self-signed certs. |
| `weak_tls_services` | Count offering weak TLS. |
| `expired_cert_services` | Count with expired certs. |
| `missing_header_ratio` | Fraction of key security headers missing (HTTP services). |
| `risk_score` | 0-100 "need": weighted security exposure. |
| `fit_score` | 0-100 market fit: geography + size proxy. |
| `total_score` | 0.6*risk + 0.4*fit. |
| `tier` | A (>=70) / B (>=50) / C (>=30) / D. |
