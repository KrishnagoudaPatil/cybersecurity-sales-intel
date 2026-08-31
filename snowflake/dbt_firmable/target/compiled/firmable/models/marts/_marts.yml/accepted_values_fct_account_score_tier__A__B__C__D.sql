
    
    

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


