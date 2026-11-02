-- Who was eligible for each request: serves the region and category this month, not paused, and had
-- used less than its monthly volume before the request. Equals mma.features.store.eligible().
with pairs as (
  select r.request_id, r.ts, r.month, c.partner_id, c.monthly_cap, c.pause_from, c.pause_to
  from {{ ref('stg_requests') }} r
  join {{ ref('int_partner_coverage') }} c on c.month = r.month and c.region = r.region and c.category = r.category
  where not (c.pause_from >= 0 and c.pause_from <= r.ts and r.ts < c.pause_to)
),
b as (
  select p.*, x.name, x.at
  from pairs p, unnest([{'name': 'now', 'at': p.ts}, {'name': 'month', 'at': p.month * 30.0}]) as u(x)
),
j as (
  select b.request_id, b.partner_id, b.monthly_cap, b.name, coalesce(c.n, 0) as n
  from b asof left join {{ ref('int_cumulative') }} c
    on c.stream = 'lead' and c.k = cast(b.partner_id as varchar) and b.at > c.ts
)
select request_id, partner_id
from j
group by request_id, partner_id, monthly_cap
having max(case when name = 'now' then n end) - max(case when name = 'month' then n end) < monthly_cap
