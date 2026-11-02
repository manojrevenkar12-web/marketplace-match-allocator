-- Daily matching KPIs per region and category: requests, matched share, leads, contacts, wins.
with r as (select * from {{ ref('stg_requests') }}),
m as (select request_id, count(*) as leads, sum(price) as revenue from {{ ref('stg_matches') }} group by request_id),
e as (
  select request_id, max(case when kind = 'contacted' then 1 else 0 end) as contacted, max(case when kind = 'won' then 1 else 0 end) as won
  from {{ ref('stg_events') }} group by request_id
)
select cast(floor(r.ts) as integer) as day, r.region, r.category,
  count(*) as requests,
  count(m.request_id) as matched,
  coalesce(sum(m.leads), 0) as leads,
  coalesce(sum(m.revenue), 0) as revenue,
  coalesce(sum(e.contacted), 0) as contacted,
  coalesce(sum(e.won), 0) as projects
from r left join m using (request_id) left join e using (request_id)
group by 1, 2, 3
