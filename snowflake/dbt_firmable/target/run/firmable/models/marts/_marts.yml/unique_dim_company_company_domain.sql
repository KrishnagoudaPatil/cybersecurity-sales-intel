
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    company_domain as unique_field,
    count(*) as n_records

from FIRMABLE.dbt_marts.dim_company
where company_domain is not null
group by company_domain
having count(*) > 1



  
  
      
    ) dbt_internal_test