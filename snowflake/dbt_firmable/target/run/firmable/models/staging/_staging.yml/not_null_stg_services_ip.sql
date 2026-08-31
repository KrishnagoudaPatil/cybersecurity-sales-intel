
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select ip
from FIRMABLE.dbt_staging.stg_services
where ip is null



  
  
      
    ) dbt_internal_test