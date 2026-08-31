
    
    

select
    company_domain as unique_field,
    count(*) as n_records

from FIRMABLE.dbt_marts.dim_company
where company_domain is not null
group by company_domain
having count(*) > 1


