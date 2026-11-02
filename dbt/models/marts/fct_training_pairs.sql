-- Training rows: features at the time of the lead and what happened after it.
select f.*,
  exists (select 1 from {{ ref('stg_events') }} e where e.request_id = f.request_id and e.partner_id = f.partner_id and e.kind = 'contacted') as contacted,
  exists (select 1 from {{ ref('stg_events') }} e where e.request_id = f.request_id and e.partner_id = f.partner_id and e.kind = 'won') as won
from {{ ref('int_pair_features') }} f
