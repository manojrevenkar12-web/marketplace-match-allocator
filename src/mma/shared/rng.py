"""Counter-based randomness: the same (request, partner, purpose) always draws the same number, so
every policy and every experiment design sees common random numbers."""

from __future__ import annotations

import numpy as np

_M = np.uint64(0x9E3779B97F4A7C15)


def _mix(x: np.ndarray) -> np.ndarray:
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def uniform(seed: int, *keys) -> np.ndarray | float:
    """Uniform in [0, 1) from integer keys (arrays broadcast)."""
    with np.errstate(over="ignore"):
        h = np.uint64(seed) * _M + np.uint64(0x2545F4914F6CDD1D)
        h = _mix(np.asarray(h, dtype=np.uint64))
        for k in keys:
            h = _mix(h ^ (np.asarray(k, dtype=np.int64).astype(np.uint64) * _M))
    out = (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)
    return float(out) if np.ndim(out) == 0 else out


def normal(seed: int, *keys) -> np.ndarray | float:
    u1 = np.maximum(uniform(seed, *keys, 1), 1e-12)
    u2 = uniform(seed, *keys, 2)
    z = np.sqrt(-2 * np.log(u1)) * np.cos(2 * np.pi * u2)
    return float(z) if np.ndim(z) == 0 else z
