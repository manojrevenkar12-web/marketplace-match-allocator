# 1. Measure matching changes with a budget split

Status: accepted

## Context

Every lead a policy sends uses up some of a partner's monthly volume. When the treatment arm and
the control arm draw on the same partners, each arm changes what the other can do: the model's
pacer sees partners filling up (from control's leads too) and raises its prices, and control gets
the partners the model left alone. The difference between the arms is then partly the arms'
competition with each other, not the effect of shipping the model.

The study runs the model everywhere and the rules everywhere on the same requests to get the true
effect, then runs four designs against it (`config/experiments.yaml`).

## Decision

Experiments on matching use the **budget split**: requests are randomised 50/50, and each arm gets
its own half of every partner's monthly volume, so the arms cannot take capacity from each other.
Standard errors are cluster-robust (the cluster is the randomised unit: the request here, the
region or the period in the other designs). An A/A run on the same split (rules in both arms) is
part of every study.

## Consequences

- The request split, the region split and the switchback are kept in the study as the comparison
  that shows why. With shared volume they report the wrong sign (see docs/REPORT.md).
- Halving each partner's volume makes each arm a smaller market. When a partner's volume is odd,
  the arm that gets the extra lead is chosen at random per partner.
- Not built yet: the serving tables reserve volume per partner and month. Running the split live
  needs an arm column in `partner_capacity`, so the database keeps each arm inside its half.
