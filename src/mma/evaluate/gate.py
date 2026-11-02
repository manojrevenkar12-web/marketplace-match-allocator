"""The release gate over generated metrics (config/release.yaml)."""

from __future__ import annotations

import json

from ..shared.config import ROOT, load, run_dir


def check(metrics: dict, rules: list[dict], missing_ok: bool = False) -> list[dict]:
    out = []
    for r in rules:
        v = metrics.get(r["name"])
        if v is None:
            ok = missing_ok
        elif r["op"] == "==":
            ok = v == r["value"]
        elif r["op"] == "<=":
            ok = v <= r["value"] + 1e-12
        else:
            ok = v >= r["value"] - 1e-12
        out.append({**r, "actual": v, "ok": bool(ok)})
    return out


def gate(profile: str) -> bool:
    p = (ROOT / "reports" / "results.json") if profile == "full" else run_dir(profile) / "results.json"
    if not p.exists():
        print(f"no results at {p}; run mma report first")
        return False
    m = json.loads(p.read_text())["metrics"]
    rel = load("release")
    ok = True
    for row in check(m, rel["floors"], missing_ok=profile != "full"):
        print(f"{'pass' if row['ok'] else 'FAIL'}  {row['name']} = {row['actual']} ({row['op']} {row['value']})")
        ok &= row["ok"]
    for row in check(m, rel["targets"], missing_ok=True):
        print(f"{'met ' if row['ok'] else 'miss'}  {row['name']} = {row['actual']} ({row['op']} {row['value']})")
    return ok
