select
  cast(partner_id as integer) as partner_id,
  cast(month as integer) as month,
  cast(home_region as varchar) as home_region,
  string_split(categories, '|') as categories,
  string_split(regions, '|') as regions,
  cast(monthly_cap as integer) as monthly_cap,
  cast(pause_from as double) as pause_from,
  cast(pause_to as double) as pause_to,
  cast(signup_day as double) as signup_day
from read_parquet('{{ var("raw") }}/partner_settings.parquet')
