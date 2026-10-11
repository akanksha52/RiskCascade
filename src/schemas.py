from dataclasses import dataclass
from typing import List

@dataclass
class RiskEvent:
    event_id: str
    entity: str
    event_type: str
    sentiment: float
    impact: int
    confidence: float
    evidence: List[str]

@dataclass
class PortfolioMetrics:
    baseline_el: float
    stressed_el: float
    delta_el: float