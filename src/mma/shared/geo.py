"""Postcode-region geography (public knowledge, config/geo.yaml)."""

from __future__ import annotations

from functools import cache

from .config import load


@cache
def _cfg():
    return load("geo")


def xy(code: str | int) -> tuple[int, int]:
    c = _cfg()
    i = int(code) - c["first_code"]
    return i % c["cols"], i // c["cols"]


def distance(a: str | int, b: str | int) -> int:
    ax, ay = xy(a)
    bx, by = xy(b)
    return max(abs(ax - bx), abs(ay - by))
