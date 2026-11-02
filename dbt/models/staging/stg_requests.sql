select
  cast(request_id as bigint) as request_id,
  cast(ts as double) as ts,
  cast(region as varchar) as region,
  cast(category as varchar) as category,
  cast(budget as varchar) as budget,
  cast(timeframe as varchar) as timeframe,
  cast(qualified as boolean) as qualified,
  cast(floor(ts / 30) as integer) as month
from read_parquet('{{ var("raw") }}/requests.parquet')
