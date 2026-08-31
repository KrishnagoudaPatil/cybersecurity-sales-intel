
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select company_domain
from FIRMABLE.dbt_marts.dim_company
where company_domain is null



  
  
      
    ) dbt_internal_test