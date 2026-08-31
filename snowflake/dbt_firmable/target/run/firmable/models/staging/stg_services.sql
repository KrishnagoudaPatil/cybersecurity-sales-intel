
  create or replace   view FIRMABLE.dbt_staging.stg_services
  
  
  
  
  as (
    -- One clean, typed row per scanned service (IP:port observation).
-- Unpacks the raw Shodan VARIANT. Kept as a view: cheap, always fresh.
with raw as (
    select v from FIRMABLE.RAW.scans
)
select
    coalesce(v:ip_str::string, v:ipv6::string)         as ip,
    (v:ipv6 is not null)                               as is_ipv6,
    v:port::int                                        as port,
    v:transport::string                                as transport,
    v:asn::string                                      as asn,
    v:org::string                                      as org,
    v:isp::string                                      as isp,
    v:_shodan:module::string                           as scan_module,
    v:timestamp::timestamp_ntz                         as observed_at,

    -- geo
    v:location:country_code::string                    as country_code,
    v:location:country_name::string                    as country_name,
    v:location:city::string                            as city,

    -- identity arrays (used downstream for entity resolution)
    v:domains                                          as domains,
    v:hostnames                                        as hostnames,
    v:tags                                              as tags,

    -- software fingerprint
    v:product::string                                  as product,
    v:version::string                                  as version,
    v:cpe23                                            as cpe23,

    -- http
    v:http:status::int                                 as http_status,
    v:http:headers                                     as http_headers,
    v:http:title::string                               as http_title,

    -- tls
    (v:ssl is not null)                                as has_tls,
    v:ssl:versions                                     as tls_versions,
    v:ssl:cert:expired::boolean                        as cert_expired,

    -- vulnerabilities: Shodan exposes both a top-level `vulns` object and opts.vulns[]
    v:vulns                                            as vulns_obj,
    v:opts:vulns                                        as opts_vulns,

    -- raw banner (free text) — the LLM reads this when structured fields are absent
    v:data::string                                     as banner,
    v                                                  as raw
from raw
-- Drop honeypots: decoy hosts, not real prospects.
where not array_contains('honeypot'::variant, v:tags)
  );

