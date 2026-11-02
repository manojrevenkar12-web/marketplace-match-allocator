import numpy as np
import pandas as pd

from mma.experiments.designs import assign, estimate
from mma.features.store import FeatureStore, eligible
from mma.matching.policies import Capacity, ModelPolicy, Pacer, RuleBaseline
from mma.models.metrics import ece
from mma.monitor.drift import psi
from mma.shared.config import load
from mma.shared.geo import distance
from mma.shared.rng import uniform
from mma.shared.types import PartnerSettings, RequestObs


def settings(n=5, cap=10):
    return {i: PartnerSettings(i, "10", frozenset({"solar"}), frozenset({"10", "11"}), cap, -1, -1, -100.0) for i in range(n)}


def req(rid=1, ts=1.5, region="10"):
    return RequestObs(rid, ts, region, "solar", "mid", "asap", True)


def test_common_random_numbers():
    assert uniform(1, 2, 3) == uniform(1, 2, 3)
    assert uniform(1, 2, 3) != uniform(1, 2, 4)
    u = uniform(9, np.arange(50_000))
    assert abs(u.mean() - 0.5) < 0.01


def test_geography():
    assert distance("10", "10") == 0
    assert distance("10", "21") == 1
    assert distance("10", "99") == 9


def test_eligibility_respects_region_pause_and_capacity():
    s = settings()
    s[1] = PartnerSettings(1, "10", frozenset({"solar"}), frozenset({"10"}), 10, 1.0, 3.0, -100.0)
    s[2] = PartnerSettings(2, "40", frozenset({"solar"}), frozenset({"40"}), 10, -1, -1, -100.0)
    st = FeatureStore(s)
    cap = {i: 10 for i in s}
    used = {3: 10}
    assert eligible(st, req(), used, cap) == [0, 4]


def test_feature_windows_count_only_the_past():
    st = FeatureStore(settings())
    for t in (0.5, 1.0, 1.4):
        st.record_lead(0, t)
    st.record_lead(0, 1.5)  # at the request time: not counted
    st.record_contact(0, 0.5, 0.9)
    x = st.features(req(ts=1.5), [0], month_start=0.0)
    names = __import__("mma.features.store", fromlist=["FEATURES"]).FEATURES
    row = dict(zip(names, x[0], strict=True))
    assert row["partner_fill"] == 3 / 10
    assert row["partner_leads_30d"] == 3
    assert row["n_candidates"] == 1


def test_rules_pick_the_least_used_partners():
    st = FeatureStore(settings())
    cap = Capacity({i: 10 for i in range(5)}, {0: 5, 1: 0, 2: 9, 3: 1, 4: 0})
    assert sorted(RuleBaseline().choose(req(), [0, 1, 2, 3, 4], cap, st, 0.0)) == [1, 3, 4]


class FixedScorer:
    def __init__(self, pc, pw):
        self.pc, self.pw = np.array(pc), np.array(pw)

    def predict(self, X):
        return self.pc[: len(X)], self.pw[: len(X)]


def test_model_policy_prefers_likely_winners_and_stops_when_value_is_negative():
    st = FeatureStore(settings())
    cap = Capacity({i: 10 for i in range(5)})
    pol = ModelPolicy(
        FixedScorer([0.9, 0.2, 0.9, 0.9, 0.9], [0.2, 0.01, 0.15, 0.1, 0.12]),
        {"revenue": 0.0, "homeowner": 1.0, "partner": 1.0},
        pacing=False,
    )
    got = pol.choose(req(), [0, 1, 2, 3, 4], cap, st, 0.0)
    assert got[0] == 0
    assert 1 not in got
    assert len(got) <= 3


def test_pacer_prices_partners_ahead_of_schedule_and_frees_those_behind():
    cfg = load("matching")
    p = Pacer(cfg)
    cap = Capacity({0: 30, 1: 30}, {0: 20, 1: 0})
    st = FeatureStore(settings(2, 30))
    for k in range(6):
        p.refresh(5.0 + k * 0.3, cap, st, 0.0)
    assert p.bid[0] > 0
    assert p.bid[1] == 0


def test_budget_split_gives_each_arm_its_own_half():
    r = pd.DataFrame({"request_id": np.arange(2000), "region": np.arange(2000) % 9, "ts": np.linspace(0, 30, 2000)})
    caps = {i: 7 + i for i in range(50)}
    a = assign("budget_split", r, caps, salt=1)
    assert a.views[0] is not a.views[1]
    for p, k in caps.items():
        assert a.views[0].cap[p] + a.views[1].cap[p] == k
        assert abs(a.views[0].cap[p] - a.views[1].cap[p]) <= 1
    assert 0.45 < a.arms.mean() < 0.55
    shared = assign("request_split", r, caps, salt=1)
    assert shared.views[0] is shared.views[1]


def test_cluster_robust_standard_errors_widen_for_clustered_designs():
    rng = np.random.default_rng(0)
    n = 6000
    region = rng.integers(0, 30, n)
    effect = rng.normal(0, 0.3, 30)[region]
    df = pd.DataFrame({"y": effect + rng.normal(0, 1, n)})
    arms_region = (region % 2).astype(int)
    iid = estimate(df, arms_region, np.arange(n), "y")
    clustered = estimate(df, arms_region, region, "y")
    assert clustered["se"] > 1.5 * iid["se"]


def test_calibration_and_drift_metrics():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 20000)
    y = (rng.uniform(0, 1, 20000) < p).astype(float)
    assert ece(y, p) < 0.02
    assert ece(y, np.clip(p * 0.5, 0, 1)) > 0.2
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 5000)) < 0.05
    assert psi(a, rng.normal(1.0, 1, 5000)) > 0.2


def test_feature_windows_equal_dbt_vars():
    import yaml

    from mma.shared.config import ROOT

    v = yaml.safe_load((ROOT / "dbt" / "dbt_project.yml").read_text())["vars"]
    c = load("features")
    for k in (
        "lead_window_days",
        "lead_lag_days",
        "win_window_days",
        "win_lead_from_days",
        "win_lead_to_days",
        "response_window_days",
        "demand_window_days",
    ):
        assert v[k] == c[k], k
    for k, x in c["prior"].items():
        assert v[f"prior_{k}"] == x, k
