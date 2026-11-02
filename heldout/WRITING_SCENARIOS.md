# Writing held-out marketplace scenarios

You are writing test worlds for a system that matches homeowner requests to partner companies
(installers, roofers, kitchen studios, estate agents) on a lead marketplace. You have **not** seen
the system and must not look at it: read only this file.

## The marketplace

- Germany is split into 90 two-digit postcode regions on a 10 x 9 grid. Demand differs by region
  (cities have more); partners are denser where demand is high, but less than proportionally, so
  rural regions are short of partners.
- Homeowners send requests in 7 categories (solar, heat pumps, windows, roofing, kitchens,
  stairlifts, real-estate sales). Each request has a budget band, a timeframe and a flag for whether
  it was qualified by phone. A hidden intent decides how likely the homeowner is to buy at all.
- Each request goes to at most 3 partners, who pay a fixed price per lead. A partner serves 1-2
  categories in its home region and up to 2 grid steps around it, and sets a monthly lead volume
  (its cap). Some partners pause for part of a month.
- After a match, each partner may call the homeowner (some call fast, some slowly, some rarely; a
  partner past 80% of its monthly volume calls less). The homeowner may buy from one of the partners
  who called and fit; the first caller has an advantage.
- The system learns from four months of logs under the current rules, then runs a fifth month. It is
  compared with the current rules on: projects won per request, lead revenue per request, partner
  profit per request and the share of homeowners who got a call.

## Scenario file format

One YAML file per scenario in `heldout/<set>/scenarios/`:

```yaml
name: short-kebab-name
about: one sentence on what this scenario stresses
seed: 12345              # any integer; distinct per scenario
overrides:               # any subset of the defaults below; nested keys merge
  partners: 800
  categories:
    solar: { share: 0.4 }
  partner:
    cap_median: 30
```

Do not change `grid`, `days_per_month`, `history_months` or the category names. Keep
`requests_per_month` between 8000 and 30000 and `partners` between 300 and 1500 (the evaluation
must finish in a few minutes per scenario).

## Defaults

```yaml
grid: { cols: 10, rows: 9 }
region_demand_sigma: 0.6       # log-normal spread of demand across regions
supply_elasticity: 0.7         # partner density ~ demand^elasticity
requests_per_month: 24000
partners: 1100
days_per_month: 30
history_months: 4
categories:
  solar:            { share: 0.30, price: 55,  intent: 0.16, margin: 2500 }
  heat_pump:        { share: 0.20, price: 65,  intent: 0.14, margin: 3000 }
  windows:          { share: 0.15, price: 35,  intent: 0.18, margin: 900 }
  roofing:          { share: 0.10, price: 45,  intent: 0.15, margin: 1500 }
  kitchen:          { share: 0.08, price: 30,  intent: 0.20, margin: 1200 }
  stairlift:        { share: 0.09, price: 50,  intent: 0.22, margin: 1400 }
  real_estate_sale: { share: 0.08, price: 300, intent: 0.10, margin: 9000 }
request:
  budget: { low: 0.35, mid: 0.45, high: 0.20 }
  budget_intent: { low: 0.7, mid: 1.0, high: 1.35 }
  timeframe: { asap: 0.30, months_3: 0.45, later: 0.25 }
  timeframe_intent: { asap: 1.4, months_3: 1.0, later: 0.55 }
  qualified_share: 0.55
  qualified_intent: 1.3
  intent_noise: 0.35
  daily_shape: [0.9, 1.15, 1.1, 1.05, 1.0, 0.85, 0.95]   # Monday..Sunday
partner:
  categories: [1, 2]           # min, max categories per partner
  radius: { 0: 0.35, 1: 0.45, 2: 0.20 }   # share of partners serving 0, 1 or 2 grid steps around home
  cap_median: 42
  cap_sigma: 0.55
  cap_min: 3
  contact_logit: { mean: 1.0, sd: 0.8 }    # how likely partners call (logit scale)
  speed_hours: { median: 6, sigma: 0.75 }  # how fast they call
  skill: { mean: 0.0, sd: 0.6 }            # how often homeowners want to buy from them
  pause_share: 0.06
outcome:
  qualified_contact: 0.4
  asap_contact: 0.3
  overload_contact: -1.5
  satisfy_bias: 0.5
  distance_penalty: 0.35
  first_contact_bonus: 0.8
  second_contact_bonus: 0.3
  win_delay_days: [7, 40]
```

## What makes a good set

Eight scenarios, each stressing something different and plausible: a market much shorter of
partners (or with far more than needed), demand concentrated in cities or spread out, partners whose
quality differs much more (or barely), partners who ignore half their leads, a category mix shifted
toward expensive leads, many partners pausing, homeowners who are far less (or more) ready to buy.
Write `heldout/<set>/README.md` listing the scenarios and what each one tests.
