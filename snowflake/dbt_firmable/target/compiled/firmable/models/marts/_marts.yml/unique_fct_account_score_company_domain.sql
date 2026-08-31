
    
    

select
    company_domain as unique_field,
    count(*) as n_records

from FIRMABLE.dbt_marts.fct_account_score
where company_domain is not null
group by company_domain
having count(*) > 1


