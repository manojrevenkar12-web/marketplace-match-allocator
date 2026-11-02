-- Running counts per partner (leads, contacts with delay sums, wins) and per region-category
-- (requests). A count "before t" is the running count of the last row with ts < t (an ASOF join),
-- exactly what bisect_left gives the online feature store.
select 'lead' as stream, cast(partner_id as varchar) as k, ts,
  row_number() over (partition by partner_id order by ts, request_id) as n, 0.0 as delay_sum
from {{ ref('stg_matches') }}
union all
select 'contact', cast(partner_id as varchar), ts,
  row_number() over (partition by partner_id order by ts, request_id),
  sum((ts - lead_ts) * 24.0) over (partition by partner_id order by ts, request_id rows between unbounded preceding and current row)
from {{ ref('stg_events') }} where kind = 'contacted'
union all
select 'win', cast(partner_id as varchar), ts,
  row_number() over (partition by partner_id order by ts, request_id), 0.0
from {{ ref('stg_events') }} where kind = 'won'
union all
select 'request', region || '|' || category, ts,
  row_number() over (partition by region, category order by ts, request_id), 0.0
from {{ ref('stg_requests') }}
