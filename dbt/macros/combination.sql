{% test dbt_utils_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% macro region_x(code) %}((cast({{ code }} as integer) - 10) % 10){% endmacro %}
{% macro region_y(code) %}((cast({{ code }} as integer) - 10) // 10){% endmacro %}
