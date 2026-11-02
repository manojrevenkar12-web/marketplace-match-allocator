select
  cast(request_id as bigint) as request_id,
  cast(partner_id as integer) as partner_id,
  cast(ts as double) as ts,
  cast(rank as integer) as rank,
  cast(policy as varchar) as policy,
  cast(price as double) as price
from read_parquet('{{ var("raw") }}/matches.parquet')
