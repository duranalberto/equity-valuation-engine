from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


GrowthModel = Literal["waterfall", "weighted_blend"]


@dataclass(frozen=True)
class GrowthSignalContribution:
    source:        str
    raw_value:     float
    clamped_value: float
    weight:        float


@dataclass(frozen=True)
class GrowthAssumption:
    requested_mode:     GrowthModel
    selected_mode:      GrowthModel
    selected_rate:      float
    selected_source:    str
    signals:            List[GrowthSignalContribution] = field(default_factory=list)
    diagnostics:        List[str] = field(default_factory=list)
    reversion_enabled:  bool = False
    long_run_growth:    Optional[float] = None


@dataclass(frozen=True)
class GrowthScenarioSet:
    scenarios:  Dict[str, List[float]]
    assumption: GrowthAssumption


@dataclass
class ValuationParams:
    """
    Base parameters shared by all valuation models.

    ``discount_rate`` is intentionally absent here — it is meaningful only
    for PE and ROE models (where it discounts future earnings to present
    value) and is a concrete field on ``PEParameters`` and ``ROEParameters``
    respectively.  ``DCFParameters`` does not discount via a fixed rate;
    it uses WACC instead.

    DESIGN-A/B: ``growth_model`` and ``reversion_enabled`` control Phase 3
    enhancements. Both default to Phase 1/2-compatible behavior. Set
    ``growth_model="weighted_blend"`` to opt into confidence-weighted growth
    blending. Set ``reversion_enabled=True`` to opt into sector mean reversion.
    ``reversion_enabled`` controls whether generate_growth_scenarios()
    applies linear mean-reversion towards the sector long-run growth rate over
    the projection window.
    """
    projection_years:  int
    margin_of_safety:  float
    growth_model:      GrowthModel = "waterfall"
    reversion_enabled: bool = False


@dataclass
class ValuationInput:
    growth_rates: List[float]


@dataclass
class ValuationResult:
    growth_rates:     List[float]
    valuation_status: str


@dataclass
class ValuationReport:
    pass
