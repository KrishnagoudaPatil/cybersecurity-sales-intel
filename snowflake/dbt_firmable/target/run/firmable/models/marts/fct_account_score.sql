
  
    

create or replace transient table FIRMABLE.dbt_marts.fct_account_score
    
    
    
    
    

    as (-- The scored prospect table: one row per company, blending observed security RISK
-- ("need") with market FIT, into a 0-100 score and an A-D tier. All deterministic SQL,
-- so ranking is auditable and reproducible. Weights are dbt vars (see dbt_project.yml).
with s as (select * from FIRMABLE.dbt_intermediate.int_service_company),

agg as (
    select
        company_domain,
        count(distinct ip)                          as host_count,
        count(*)                                    as service_count,
        sum(cve_count)                              as total_cves,
        count_if(has_known_cve)                     as services_with_cve,
        count_if(is_eol)                            as eol_services,
        count_if(is_self_signed)                    as self_signed_services,
        count_if(exposed_database)                  as exposed_db_services,
        count_if(exposed_remote_access)             as exposed_remote_services,
        count_if(weak_tls)                          as weak_tls_services,
        count_if(cert_expired)                      as expired_cert_services,
        count_if(is_http)                           as http_services,
        sum(missing_hsts + missing_csp + missing_xfo + missing_xcto) as missing_header_points,
        mode(country_code)                          as primary_country
    from s
    group by 1
),

scored as (
    select
        *,
        -- header hygiene: fraction of the 4 key headers missing across http services (0..1)
        iff(http_services > 0, missing_header_points / (http_services * 4.0), 0) as missing_header_ratio,

        -- NEED (0-100): direct, evidence-based security risk
        least(100,
              total_cves               * 15
            + exposed_db_services       * 20
            + exposed_remote_services   * 8
            + eol_services              * 12
            + self_signed_services      * 5
            + weak_tls_services         * 5
            + expired_cert_services     * 8
            + iff(http_services > 0, missing_header_points / (http_services * 4.0) * 20, 0)
        ) as risk_score
    from agg
),

fit as (
    select
        *,
        -- market fit: in target geography + company size proxy
        100 * (
            0.5 * iff(primary_country in ('AU','NZ'), 1.0, 0.5)
          + 0.5 * case
                    when host_count >= 50 then 1.0
                    when host_count >= 10 then 0.9
                    when host_count >= 3  then 0.6
                    else 0.35
                  end
        ) as fit_score
    from scored
)

select
    company_domain,
    host_count, service_count, primary_country,
    total_cves, services_with_cve, exposed_db_services, exposed_remote_services,
    eol_services, self_signed_services, weak_tls_services, expired_cert_services,
    round(missing_header_ratio, 2)                          as missing_header_ratio,
    round(risk_score, 1)                                    as risk_score,
    round(fit_score, 1)                                     as fit_score,
    -- blended: need weighted above fit (the point is who needs it NOW)
    round(0.6 * risk_score + 0.4 * fit_score, 1)            as total_score,
    case
        when 0.6 * risk_score + 0.4 * fit_score >= 70 then 'A'
        when 0.6 * risk_score + 0.4 * fit_score >= 50 then 'B'
        when 0.6 * risk_score + 0.4 * fit_score >= 30 then 'C'
        else 'D'
    end                                                     as tier
from fit
    )
;


  