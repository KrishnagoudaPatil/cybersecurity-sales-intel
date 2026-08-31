
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        tier as value_field,
        count(*) as n_records

    from FIRMABLE.dbt_marts.fct_account_score
    group by tier

)

select *
from all_values
where value_field not in (
    'A','B','C','D'
)



  
  
      
    ) dbt_internal_test