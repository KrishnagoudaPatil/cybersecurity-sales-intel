-- Entity resolution: attribute each scanned service to the company that actually
-- operates it, via a CONFIDENCE-RANKED WATERFALL of signals (best -> weakest):
--   1. TLS cert subject CN  — the tenant provisions its own cert, so it names the
--      real company regardless of who owns the IP. Trusted even on cloud/hosting IPs.
--   2. HTTP Host            — when the host advertises a real domain (not the bare IP).
--   3. Reverse-DNS domains  — only when the host's ORG is not a hosting/telco provider
--      (a provider PTR names the provider, not the customer -> "fails open").
-- Every candidate is normalised to its registrable domain (eTLD+1) and screened against
-- the infra_domains seed. The winner carries its source + confidence for auditability.
-- Services with no attributable company drop out (unattributed).

with sig as (
    -- one row per service (ip, port); keep the most recent observation
    select * from {{ ref('int_service_signals') }}
    qualify row_number() over (partition by ip, port order by observed_at desc nulls last) = 1
),

-- services whose network ORG looks like a hosting/CDN/telco provider (LIKE-join to the
-- pattern seed). Used to distrust the reverse-DNS signal for those hosts.
org_infra as (
    select distinct s.ip, s.port
    from sig s
    join {{ ref('infra_org_patterns') }} p
      on lower(coalesce(s.org, '')) like '%' || lower(p.pattern) || '%'
),

sig2 as (
    select s.*, (oi.ip is not null) as is_infra_org
    from sig s
    left join org_infra oi using (ip, port)
),

candidates as (
    -- 1) TLS cert CN — trusted regardless of org
    select ip, port, {{ registrable_domain('cert_cn') }} as cand,
           'cert' as source, 0.9 as conf
    from sig2
    where cert_cn is not null

    union all

    -- 2) HTTP Host — only if it is a hostname, not the bare IP
    select ip, port, {{ registrable_domain("split_part(http_host, ':', 1)") }} as cand,
           'http' as source, 0.6 as conf
    from sig2
    where http_host is not null
      and http_host like '%.%'
      and http_host rlike '[a-z]'
      and not http_host rlike '^[0-9.]+$'

    union all

    -- 3) reverse-DNS domains — distrusted when the host org is a provider
    select s.ip, s.port, {{ registrable_domain('d.value::string') }} as cand,
           'rdns' as source, 0.5 as conf
    from sig2 s, lateral flatten(input => s.domains) d
    where not s.is_infra_org
),

filtered as (
    -- drop null/degenerate candidates, invalid/placeholder domains (default & self-
    -- signed certs love these), bare public suffixes, and known infrastructure domains
    select c.*
    from candidates c
    left join {{ ref('infra_domains') }} i on lower(c.cand) = lower(i.domain)
    where c.cand is not null
      and c.cand <> ''
      and i.domain is null
      and not c.cand rlike '^[0-9.]+$'                                  -- IP-like / numeric
      and split_part(c.cand, '.', -1) not in                           -- reserved / non-public TLDs
          ('local','localdomain','lan','internal','corp','home','gateway',
           'invalid','example','test','arpa','localhost','host','router','modem','default')
      and lower(c.cand) not in ('example.com','example.org','example.net','localhost','test.com')
      and c.cand not in {{ public_suffix_two_level() }}                 -- bare eTLD (PSL gap)
),

ranked as (
    -- one company per service: highest-confidence signal wins, then shortest domain
    select *,
           row_number() over (partition by ip, port
                              order by conf desc, length(cand), cand) as rn
    from filtered
),

pick as (
    select ip, port,
           cand   as company_domain,
           source as attribution_source,
           conf   as attribution_confidence
    from ranked
    where rn = 1
)

select
    sig2.* exclude (domains, hostnames, tags, cve_ids, banner, version,
                    cert_cn, cert_o, http_host, is_infra_org),
    sig2.cert_o as company_name,          -- cert subject O: the real company name, when present
    p.company_domain,
    p.attribution_source,
    p.attribution_confidence
from sig2
join pick p using (ip, port)
