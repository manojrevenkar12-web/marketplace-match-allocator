"""Shipping code decides from what the platform can see: it never imports the simulator or the
evaluation, and never reads config/world.yaml."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIPPING = ["shared", "data", "features", "models", "matching", "experiments", "serve", "monitor", "pipeline.py"]


def files():
    for s in SHIPPING:
        p = ROOT / "src" / "mma" / s
        yield from ([p] if p.suffix == ".py" else sorted(p.rglob("*.py")))


def test_shipping_code_never_reads_the_truth():
    for f in files():
        text = f.read_text()
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
                assert "sim" not in mod.split(".") and "evaluate" not in mod.split("."), f"{f}: {mod}"
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert not a.name.startswith(("mma.sim", "mma.evaluate")), f"{f}: {a.name}"
        assert "world.yaml" not in text.replace("load it through mma.sim.world.world_config()", "") or f.name == "config.py", f


def test_config_loader_refuses_the_truth():
    import pytest

    from mma.shared.config import load

    with pytest.raises(PermissionError):
        load("world")


def test_airflow_dag_runs_the_pipeline_in_order():
    tree = ast.parse((ROOT / "airflow" / "dags" / "matching_pipeline.py").read_text())
    chain = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.RShift)]
    names = []

    def flatten(n):
        if isinstance(n, ast.BinOp):
            flatten(n.left)
            flatten(n.right)
        else:
            names.append(n.id)

    flatten(max(chain, key=lambda n: len(ast.dump(n))))
    assert names == ["land", "build", "parity", "monday", "train", "promote", "monitor"]
