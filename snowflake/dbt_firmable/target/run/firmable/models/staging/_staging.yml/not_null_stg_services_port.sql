
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select port
from FIRMABLE.dbt_staging.stg_services
where port is null



  
  
      
    ) dbt_internal_test