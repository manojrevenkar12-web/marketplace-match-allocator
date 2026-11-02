# Held-out scenarios, set v1

Written blind from `heldout/WRITING_SCENARIOS.md` only, without looking at the matching system,
its configuration, tests or results. Each scenario overrides a few defaults; everything else
(grid, days per month, four history months, category names) is unchanged.

| File | Name | Seed | What it tests |
|---|---|---|---|
| `scenarios/01-partner-shortage.yaml` | partner-shortage | 40117 | Severe shortage: 28,000 requests a month for 350 partners with smaller caps; requests compete for a pool that is exhausted early in the month. |
| `scenarios/02-partner-glut.yaml` | partner-glut | 52903 | Oversupply: 9,000 requests for 1,500 partners with larger caps; capacity is never the limit, choosing the best three partners is. |
| `scenarios/03-city-concentrated.yaml` | city-concentrated | 61448 | Demand concentrated in cities (region spread 1.3 instead of 0.6) with partner density following it weakly (elasticity 0.45), so rural regions are badly short and cities crowded. |
| `scenarios/04-wide-quality-spread.yaml` | wide-quality-spread | 73021 | Partners differ much more in skill (sd 1.5), willingness to call (sd 1.6) and call speed (sigma 1.3); good and bad partners are far apart. |
| `scenarios/05-ignored-leads.yaml` | ignored-leads | 84556 | Partners call only about half their leads (contact logit mean 0.0) and slowly (median 14 h); tests the share of homeowners who get any call. |
| `scenarios/06-expensive-lead-mix.yaml` | expensive-lead-mix | 90233 | Mix shifted to expensive leads: real-estate sales 25% and heat pumps 28%; lead revenue and partner profit swing on few high-price leads. |
| `scenarios/07-frequent-pauses.yaml` | frequent-pauses | 17789 | 35% of partners pause for part of a month (default 6%); capacity learned from history is unreliable. |
| `scenarios/08-hesitant-homeowners.yaml` | hesitant-homeowners | 28364 | Homeowners far less ready to buy: category intents halved, 35% phone-qualified, 15% asap and 45% later; few leads become projects and partner profit is thin. |

Seeds are distinct. `requests_per_month` stays within 8,000-30,000 and `partners` within 300-1,500
in every scenario.
