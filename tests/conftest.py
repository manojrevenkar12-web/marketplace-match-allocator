import os

import pytest

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


@pytest.fixture(scope="session")
def small(tmp_path_factory):
    """A small world with four months of logged history and a built warehouse."""
    from mma.data.warehouse import build
    from mma.sim.history import build_history
    from mma.sim.world import World, world_config

    d = tmp_path_factory.mktemp("small")
    w = World(world_config({"requests_per_month": 1500, "partners": 120}), 3)
    market = build_history(w, w.cfg["history_months"], d / "raw")
    dbt = build(d / "raw", d / "warehouse.duckdb")
    return {"dir": d, "world": w, "market": market, "dbt": dbt}
