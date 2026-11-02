-- Point-in-time features for every delivered lead (request x partner), computed only from events
-- before the request. Same definitions as the online feature store (config/features.yaml).
with pairs as (
  select m.request_id, m.partner_id, r.ts as t, r.month, r.region, r.category, r.budget, r.timeframe, r.qualified,
    s.home_region, s.monthly_cap, s.signup_day, len(s.categories) as ncats
  from {{ ref('stg_matches') }} m
  join {{ ref('stg_requests') }} r using (request_id)
  join {{ ref('stg_partner_settings') }} s on s.partner_id = m.partner_id and s.month = r.month
),
b as (
  select p.request_id, p.partner_id, x.name, x.stream, x.k, x.at
  from pairs p, unnest([
    {'name': 'lead_now',      'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t},
    {'name': 'lead_month',    'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.month * 30.0},
    {'name': 'lead_30',       'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t - 30},
    {'name': 'lead_ctr_hi',   'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('lead_lag_days') }}},
    {'name': 'lead_ctr_lo',   'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('lead_window_days') }} - {{ var('lead_lag_days') }}},
    {'name': 'lead_win_hi',   'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('win_lead_to_days') }}},
    {'name': 'lead_win_lo',   'stream': 'lead',    'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('win_lead_from_days') }}},
    {'name': 'contact_now',   'stream': 'contact', 'k': cast(p.partner_id as varchar), 'at': p.t},
    {'name': 'contact_lo',    'stream': 'contact', 'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('lead_window_days') }}},
    {'name': 'resp_lo',       'stream': 'contact', 'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('response_window_days') }}},
    {'name': 'win_now',       'stream': 'win',     'k': cast(p.partner_id as varchar), 'at': p.t},
    {'name': 'win_lo',        'stream': 'win',     'k': cast(p.partner_id as varchar), 'at': p.t - {{ var('win_window_days') }}},
    {'name': 'req_now',       'stream': 'request', 'k': p.region || '|' || p.category, 'at': p.t},
    {'name': 'req_lo',        'stream': 'request', 'k': p.region || '|' || p.category, 'at': p.t - {{ var('demand_window_days') }}}
  ]) as u(x)
),
j as (
  select b.request_id, b.partner_id, b.name, coalesce(c.n, 0) as n, coalesce(c.delay_sum, 0.0) as d
  from b asof left join {{ ref('int_cumulative') }} c on c.stream = b.stream and c.k = b.k and b.at > c.ts
),
w as (
  select request_id, partner_id,
    {% for nm in ['lead_now','lead_month','lead_30','lead_ctr_hi','lead_ctr_lo','lead_win_hi','lead_win_lo','contact_now','contact_lo','resp_lo','win_now','win_lo','req_now','req_lo'] %}
    max(case when name = '{{ nm }}' then n end) as {{ nm }},
    {% endfor %}
    max(case when name = 'contact_now' then d end) as dsum_now,
    max(case when name = 'resp_lo' then d end) as dsum_lo
  from j group by request_id, partner_id
),
supply as (
  select month, region, category, sum(monthly_cap) as supply
  from {{ ref('int_partner_coverage') }} group by month, region, category
),
cands as (
  select request_id, count(*) as n_candidates from {{ ref('int_candidates') }} group by request_id
)
select
  p.request_id, p.partner_id, p.t as ts, p.month,
  cast(list_position(['solar','heat_pump','windows','roofing','kitchen','stairlift','real_estate_sale'], p.category) - 1 as double) as category,
  cast(list_position(['low','mid','high'], p.budget) - 1 as double) as budget,
  cast(list_position(['asap','months_3','later'], p.timeframe) - 1 as double) as timeframe,
  cast(p.qualified as double) as qualified,
  (p.t - floor(p.t)) * 24.0 as hour,
  cast(greatest(abs({{ region_x('p.home_region') }} - {{ region_x('p.region') }}), abs({{ region_y('p.home_region') }} - {{ region_y('p.region') }})) as double) as distance,
  cast(p.monthly_cap as double) as partner_cap,
  (w.lead_now - w.lead_month) / p.monthly_cap as partner_fill,
  cast(w.lead_now - w.lead_30 as double) as partner_leads_30d,
  ((w.contact_now - w.contact_lo) + {{ var('prior_contact_rate') }} * {{ var('prior_contact_weight') }})
    / ((w.lead_ctr_hi - w.lead_ctr_lo) + {{ var('prior_contact_weight') }}) as partner_contact_rate,
  ((w.win_now - w.win_lo) + {{ var('prior_win_rate') }} * {{ var('prior_win_weight') }})
    / ((w.lead_win_hi - w.lead_win_lo) + {{ var('prior_win_weight') }}) as partner_win_rate,
  ((w.dsum_now - w.dsum_lo) + {{ var('prior_response_hours') }} * 2) / ((w.contact_now - w.resp_lo) + 2) as partner_response_hours,
  p.t - p.signup_day as partner_tenure_days,
  cast(p.ncats as double) as partner_ncats,
  case when s.supply > 0 then (w.req_now - w.req_lo) * (30.0 / {{ var('demand_window_days') }}) / s.supply else 99.0 end as region_pressure,
  cast(coalesce(c.n_candidates, 0) as double) as n_candidates
from pairs p
join w using (request_id, partner_id)
left join supply s on s.month = p.month and s.region = p.region and s.category = p.category
left join cands c on c.request_id = p.request_id
