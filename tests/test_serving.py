"""The matching service against Postgres: no partner is ever oversold, retries are idempotent."""

import os

import pytest

pytestmark = [pytest.mark.db, pytest.mark.slow]
DSN = os.environ.get("MMA_TEST_DATABASE_URL")


@pytest.mark.skipif(not DSN, reason="needs MMA_TEST_DATABASE_URL")
def test_two_instances_racing_never_oversell(small):
    from mma.evaluate.serving_bench import bench

    r = bench(DSN, small["dir"] / "raw", None, small["world"], n=600, threads=8, squeeze=1)
    assert r["oversold_leads"] == 0
    assert r["decisions_vs_counter_mismatches"] == 0
    assert r["retry_returns_same_decision"]
    assert r["leads"] > 0


@pytest.mark.skipif(not DSN, reason="needs MMA_TEST_DATABASE_URL")
def test_events_need_a_known_lead(small):
    from fastapi import HTTPException

    from mma.evaluate.serving_bench import reset
    from mma.serve.app import EventIn, Service

    reset(DSN)
    s = Service(DSN, small["dir"] / "raw")
    with pytest.raises(HTTPException):
        s.event(EventIn(request_id=1, partner_id=1, kind="won", ts=1.0))
