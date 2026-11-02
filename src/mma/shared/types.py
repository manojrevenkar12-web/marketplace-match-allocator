"""What the platform sees about a request and about a partner's settings."""

from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = ["solar", "heat_pump", "windows", "roofing", "kitchen", "stairlift", "real_estate_sale"]
BUDGETS = ["low", "mid", "high"]
TIMEFRAMES = ["asap", "months_3", "later"]
MAX_PARTNERS = 3


@dataclass(frozen=True)
class RequestObs:
    request_id: int
    ts: float  # days
    region: str
    category: str
    budget: str
    timeframe: str
    qualified: bool


@dataclass
class PartnerSettings:
    partner_id: int
    home_region: str
    categories: frozenset[str]
    regions: frozenset[str]
    monthly_cap: int
    pause_from: float
    pause_to: float
    signup_day: float

    def paused(self, ts: float) -> bool:
        return self.pause_from >= 0 and self.pause_from <= ts < self.pause_to
