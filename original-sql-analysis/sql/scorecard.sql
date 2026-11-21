select min(day) first_day, max(day) last_day, count(*) us_lines,
 count(distinct store) stores, count(distinct case when kind='Sale' then invoice end) sale_invoices,
 round(sum(case when kind='Sale' then amount else 0 end),2) sale_revenue,
 round(-sum(case when kind='Return' then amount else 0 end),2) refunds,
 round(sum(amount),2) net_revenue,
 round(sum(case when kind='Sale' then amount else 0 end) /
 count(distinct case when kind='Sale' then invoice end),2) sale_aov
from sales
