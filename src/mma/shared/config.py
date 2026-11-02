"""Settings live in config/*.yaml. Shipping code never loads world.yaml (the truth)."""

from __future__ import annotations

import copy
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config"


@cache
def _load(name: str) -> dict[str, Any]:
    with open(CONFIG / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def load(name: str) -> dict[str, Any]:
    if name == "world":
        raise PermissionError("world.yaml is the truth; load it through mma.sim.world.world_config()")
    return copy.deepcopy(_load(name))


def deep_merge(a: dict[str, Any], b: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def run_dir(profile: str) -> Path:
    d = ROOT / "runs" / profile
    d.mkdir(parents=True, exist_ok=True)
    return d
