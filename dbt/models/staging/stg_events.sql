select
  cast(e.request_id as bigint) as request_id,
  cast(e.partner_id as integer) as partner_id,
  cast(e.kind as varchar) as kind,
  cast(e.ts as double) as ts,
  m.ts as lead_ts
from read_parquet('{{ var("raw") }}/events.parquet') e
join {{ ref('stg_matches') }} m using (request_id, partner_id)
