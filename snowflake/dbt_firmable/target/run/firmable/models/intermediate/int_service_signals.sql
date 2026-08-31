
  create or replace   view FIRMABLE.dbt_intermediate.int_service_signals
  
  
  
  
  as (
    -- Per-service security findings. This is the DETERMINISTIC signal layer (the "rules"
-- half of the rule-vs-LLM split), expressed as SQL so it scales to the full 74GB.
with s as (
    select * from FIRMABLE.dbt_staging.stg_services
),
enriched as (
    select
        *,
        -- CVE ids come from two Shodan locations; union + de-dupe.
        array_distinct(array_cat(
            coalesce(object_keys(vulns_obj), array_construct()),
            coalesce(opts_vulns, array_construct())
        ))                                                              as cve_ids,
        -- lowercased, comma-joined header keys for case-insensitive presence checks
        lower(coalesce(array_to_string(object_keys(http_headers), ','), '')) as hdr_keys
    from s
)
select
    ip, port, transport, org, isp, asn,
    country_code, country_name, city,
    domains, hostnames, tags, product, version, banner, observed_at,

    array_size(cve_ids)                                         as cve_count,
    (array_size(cve_ids) > 0)                                   as has_known_cve,
    cve_ids,

    array_contains('eol-product'::variant, tags)               as is_eol,
    array_contains('self-signed'::variant, tags)               as is_self_signed,
    array_contains('vpn'::variant, tags)                       as is_vpn,
    array_contains('iot'::variant, tags)                       as is_iot,

    -- exposed sensitive services
    (array_contains('database'::variant, tags)
        or port in (3306,5432,27017,6379,9200,1433,5984,11211,9042,7000,8123)
        or product ilike any ('%mysql%','%mongo%','%redis%','%elastic%','%postgres%','%cassandra%')
    )                                                          as exposed_database,
    (port in (3389,23,5900,21))                                as exposed_remote_access,  -- RDP/telnet/VNC/FTP

    -- weak transport security
    has_tls,
    (array_contains('TLSv1'::variant, tls_versions)
        or array_contains('TLSv1.1'::variant, tls_versions)
        or array_contains('SSLv3'::variant, tls_versions)
        or array_contains('SSLv2'::variant, tls_versions))     as weak_tls,
    coalesce(cert_expired, false)                              as cert_expired,

    -- missing HTTP security headers (only meaningful for http services)
    (http_status is not null)                                  as is_http,
    iff(http_status is not null and hdr_keys not like '%strict-transport-security%', 1, 0) as missing_hsts,
    iff(http_status is not null and hdr_keys not like '%content-security-policy%',   1, 0) as missing_csp,
    iff(http_status is not null and hdr_keys not like '%x-frame-options%',           1, 0) as missing_xfo,
    iff(http_status is not null and hdr_keys not like '%x-content-type-options%',    1, 0) as missing_xcto
from enriched
  );

