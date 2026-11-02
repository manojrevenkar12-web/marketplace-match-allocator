# 2. One euro objective, with a price on scarce partner volume

Status: accepted

## Context

A match has to serve three groups: homeowners want a partner who calls and does the job, partners
want leads they can win at the price they pay, and the platform earns per lead. Product, partner
and leadership teams will each ask for a different balance.

Greedy scoring (send each request to the best-scoring partners) uses up the best partners early in
the month and leaves later requests with nobody.

## Decision

- Each candidate set is scored in euros: lead revenue, plus the value of the homeowner's project
  (with diminishing returns: a second partner adds less than the first), plus the partner's expected
  profit. The weights are presets in `config/matching.yaml` (balanced, revenue first, homeowner
  first, partner first), so a trade-off is a configuration change that the release gate checks.
- Partner volume has a price in euros (a dual variable), raised when a partner is ahead of an even
  monthly schedule and lowered when behind, recomputed every six hours.
- Probabilities come from calibrated models (ADR 3), because the objective multiplies them by
  euros.

## Consequences

- The frontier in docs/REPORT.md shows what each preset gives and gives up on the same requests.
- Partner margins are assumptions in config; before use they need the partner category managers'
  numbers.
- Without pacing the model does worse than the rules on projects and revenue; the gate keeps a
  check that the balanced preset holds revenue.
