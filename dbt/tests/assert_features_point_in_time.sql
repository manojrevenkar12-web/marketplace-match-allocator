-- No feature may use events from the request's own time or later: a partner's fill can only count
-- leads delivered before the request, so it never exceeds its monthly volume, and the request's own
-- partners must have been eligible.
select f.request_id, f.partner_id
from {{ ref('fct_training_pairs') }} f
left join {{ ref('int_candidates') }} c using (request_id, partner_id)
where f.partner_fill >= 1.0 or c.partner_id is null
