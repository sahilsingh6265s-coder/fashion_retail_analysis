-- Same categories, same weekdays, two weeks each. Descriptive period comparison.
with eligible as (
 select distinct Category, subcategory from calendar
 where Start='2024-03-15' and End='2024-03-31' and Discont=0.35
)
select case when s.day<'2024-03-15' then '01_prior' else '02_promotion' end period,
 sum(s.units) sold_units, round(sum(s.amount),2) sale_revenue,
 round(sum(s.amount-s.cost*s.units),2) estimated_contribution,
 round(100.0*sum(case when s.discount=.35 then s.units else 0 end)/sum(s.units),2) pct_units_at_35_discount
from sales s join eligible e on s.category=e.Category and s.subcategory=e.subcategory
where s.kind='Sale' and s.day between '2024-03-01' and '2024-03-28'
group by period order by period
