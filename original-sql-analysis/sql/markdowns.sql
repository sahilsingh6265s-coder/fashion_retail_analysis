-- Compare within a category and subcategory. Margin is a production-cost proxy.
select category, subcategory, round(100*discount) discount_pct, sum(units) units,
 count(distinct invoice) baskets, round(sum(amount),2) sale_revenue,
 round(sum(amount)/sum(units),2) selling_price_per_unit,
 round(sum(amount-units*cost)/sum(units),2) contribution_per_unit,
 round(100*sum(amount-units*cost)/nullif(sum(amount),0),2) margin_proxy_pct
from sales where kind='Sale'
group by category,subcategory,discount order by category,subcategory,discount
