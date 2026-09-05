-- One row per resolved company (by primary domain), with company-level aggregates
-- derived purely from its observed internet footprint.
with s as (select * from {{ ref('int_service_company') }})
select
    company_domain,
    mode(company_name)                      as company_name,        -- from TLS cert subject O, when present
    max(attribution_confidence)             as attribution_confidence,
    count(distinct ip)                      as host_count,
    count(*)                                as service_count,
    count(distinct port)                    as distinct_ports,
    mode(country_code)                      as primary_country,
    mode(org)                               as primary_hosting_org,
    max(observed_at)                        as last_seen,
    case
        when count(distinct ip) >= 50 then 'enterprise'
        when count(distinct ip) >= 10 then 'mid'
        when count(distinct ip) >= 3  then 'small'
        else 'micro'
    end                                     as size_band
from s
group by 1
