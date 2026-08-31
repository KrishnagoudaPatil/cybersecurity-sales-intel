
  
    

create or replace transient table FIRMABLE.dbt_marts.dim_company
    
    
    
    
    

    as (-- One row per resolved company (by primary domain), with firmographic-style aggregates
-- derived purely from its observed internet footprint.
with s as (select * from FIRMABLE.dbt_intermediate.int_service_company)
select
    company_domain,
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
    )
;


  