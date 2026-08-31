
  create or replace   view FIRMABLE.dbt_intermediate.int_service_company
  
  
  
  
  as (
    -- Entity resolution: attribute each scanned service to a single "company", proxied by
-- its primary registrable domain. Infra/CDN/hosting domains are excluded (they are the
-- host, not the customer). Services with no attributable domain drop out (unattributed).
with svc as (
    select * from FIRMABLE.dbt_intermediate.int_service_signals
),
exploded as (
    select svc.*, d.value::string as domain
    from svc, lateral flatten(input => svc.domains) d
),
filtered as (
    select e.*
    from exploded e
    left join FIRMABLE.dbt_seeds.infra_domains infra
      on lower(e.domain) = lower(infra.domain)
    where e.domain is not null
      and infra.domain is null
),
ranked as (
    -- one domain per service: prefer the shortest (most registrable-looking) name
    select *,
           row_number() over (partition by ip, port order by length(domain), domain) as rn
    from filtered
)
select * exclude (rn, domain, domains, hostnames, tags, cve_ids, banner, version),
       domain as company_domain
from ranked
where rn = 1
  );

