with totals as (
 select category,subcategory,product,style,sum(amount) net_revenue,
 sum(case when kind='Sale' then units else -units end) net_units
 from sales group by category,subcategory,product,style
), ranked as (
 select *,row_number() over(partition by category order by net_revenue desc,product) as rank
 from totals)
select category,rank,subcategory,product,style,net_units,round(net_revenue,2) net_revenue
from ranked where rank<=10 order by category,rank
