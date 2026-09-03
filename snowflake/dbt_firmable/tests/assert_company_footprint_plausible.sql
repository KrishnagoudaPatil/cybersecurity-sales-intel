-- Fails-open guardrail for entity resolution. A single real company rarely operates
-- more than ~150 distinct internet-facing hosts under one registrable domain; when it
-- does, it usually means infrastructure (a hosting/CDN/ISP domain) leaked past the
-- infra filters and glued many unrelated hosts into a phantom company. This surfaces
-- as a WARNING (not an error) so new infra shows up as a failing test to investigate,
-- instead of silently polluting the marts. Raise the threshold or seed the offender
-- once reviewed.
{{ config(severity = 'warn') }}

select company_domain, host_count, primary_hosting_org
from {{ ref('dim_company') }}
where host_count > 150
order by host_count desc
