"""The data foundation, models and pipeline on a small world (dbt, parity, MLflow gate)."""

import json

import numpy as np
import pytest

from mma.data.warehouse import training_pairs
from mma.features.replay import replay
from mma.features.store import FEATURES

pytestmark = pytest.mark.slow


def test_dbt_build_and_tests_pass(small):
    assert small["dbt"]["failed"] == 0
    assert small["dbt"]["tests"] >= 10


def test_training_features_equal_serving_features(small):
    pairs = training_pairs(small["dir"] / "warehouse.duckdb")
    _, online, _ = replay(small["dir"] / "raw")
    j = online.merge(pairs, on=["request_id", "partner_id"], suffixes=("_on", "_off"))
    assert len(j) == len(pairs) == len(online) > 1000
    for f in FEATURES:
        assert np.allclose(j[f + "_on"], j[f + "_off"], rtol=1e-9, atol=1e-9), f


def test_pipeline_trains_registers_and_promotes_through_the_gate(small, tmp_path):
    from mma import pipeline
    from mma.models import registry

    w = small["world"]
    cutoff = w.cfg["history_months"] * w.days
    parity = pipeline.step_parity(small["dir"] / "raw", small["dir"] / "warehouse.duckdb")
    assert parity["mismatches"] == 0
    cand = pipeline.step_train(small["dir"] / "warehouse.duckdb", cutoff, tmp_path / "mlflow", parity)
    assert cand["version"] == "1"
    promoted = pipeline.step_promote({**cand, "passed": True}, tmp_path / "mlflow")
    assert promoted["promoted"]
    scorer = registry.load_champion(tmp_path / "mlflow")
    pc, pw = scorer.predict(np.zeros((3, len(FEATURES))))
    assert pc.shape == (3,) and (0 <= pw).all() and (pw <= 1).all()
    mon = pipeline.step_monitor(small["dir"] / "warehouse.duckdb", tmp_path / "mlflow", cutoff)
    assert set(mon["psi"]) == set(FEATURES)
    json.dumps(mon)


def test_gate_refuses_a_badly_calibrated_or_skewed_candidate():
    from mma.models.registry import gate

    good = {"contact_ece": 0.01, "contact_auc": 0.72, "win_ece": 0.005, "win_auc": 0.65}
    assert gate(good, None, 0)[0]
    assert not gate({**good, "contact_ece": 0.2}, None, 0)[0]
    assert not gate(good, None, 3)[0]
    assert not gate(good, {"contact_auc": 0.80, "win_auc": 0.65}, 0)[0]
