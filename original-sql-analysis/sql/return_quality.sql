select count(*) repeated_return_keys, sum(n-1) excess_rows_at_this_key
from (select invoice,line,count(*) n from lines where kind='Return'
      group by invoice,line having count(*)>1)
