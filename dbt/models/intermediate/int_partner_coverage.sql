-- one row per partner, month, region and category it serves
select s.partner_id, s.month, r.region, c.category, s.monthly_cap, s.pause_from, s.pause_to
from {{ ref('stg_partner_settings') }} s,
  unnest(s.regions) as r(region),
  unnest(s.categories) as c(category)
