"""
domain/valuation/models/summary.py

DESIGN-D: ValuationSummaryReport — a consolidated cross-model view produced
after all valuation managers have run for a given ticker.

Provides:
  - Per-model Bear / Base / Bull intrinsic values and statuses
  - composite_intrinsic: equal-weight average of all Base intrinsics
  - model_agreement_score: std-dev of Base intrinsics normalised by current price
    (lower = models agree; higher = wide disagreement)
  - confidence_band: composite ± 1 std-dev (tuple of lo, hi)
  - implied_upside: (composite_intrinsic / current_price) − 1
  - A human-readable note when no models could produce an intrinsic value
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ModelScenarioRow:
    """Single model × scenario intrinsic value entry."""
    model_name:        str
    scenario:          str            # "Bear" | "Base" | "Bull"
    intrinsic_value:   float
    valuation_status:  str            # "undervalued" | "reasonable" | "overvalued"
    implied_upside:    float          # (intrinsic / current_price) - 1


@dataclass
class ValuationSummaryReport:
    """
    Consolidated cross-model valuation summary.

    Computed by cli/main.py after all managers have completed their
    execute_valuation_scenarios() calls.

    Fields
    ------
    ticker : str
        The ticker symbol.
    current_price : float
        Market price at the time of valuation.
    rows : list of ModelScenarioRow
        One entry per (model, scenario) pair that ran successfully.
    composite_intrinsic : float | None
        Equal-weight average of all Base-scenario intrinsics from models
        that ran.  None when no models produced a result.
    model_agreement_score : float | None
        Standard deviation of Base intrinsics normalised by current_price.
        0.0 = perfect agreement; > 0.5 = high dispersion.
    confidence_band : (float, float) | None
        (composite_intrinsic − σ, composite_intrinsic + σ) where σ is the
        un-normalised std-dev of Base intrinsics.
    implied_upside : float | None
        (composite_intrinsic / current_price) − 1.
        Positive = composite suggests undervaluation.
    models_run : list[str]
        Names of models that completed (regardless of valuation status).
    models_skipped : list[str]
        Names of models that were skipped (suitability check failed).
    note : str
        Human-readable summary note — especially useful when no models ran.
    """

    ticker:                str
    current_price:         float
    rows:                  List[ModelScenarioRow]          = field(default_factory=list)
    composite_intrinsic:   Optional[float]                 = None
    model_agreement_score: Optional[float]                 = None
    confidence_band:       Optional[Tuple[float, float]]   = None
    implied_upside:        Optional[float]                 = None
    models_run:            List[str]                       = field(default_factory=list)
    models_skipped:        List[str]                       = field(default_factory=list)
    note:                  str                             = ""

    @classmethod
    def build(
        cls,
        ticker: str,
        current_price: float,
        rows: List[ModelScenarioRow],
        models_run: List[str],
        models_skipped: List[str],
    ) -> "ValuationSummaryReport":
        """
        Compute composite_intrinsic, model_agreement_score, confidence_band,
        and implied_upside from the supplied rows.
        """
        base_intrinsics = [
            r.intrinsic_value for r in rows if r.scenario == "Base"
        ]

        composite: Optional[float] = None
        agreement: Optional[float] = None
        band:      Optional[Tuple[float, float]] = None
        upside:    Optional[float] = None

        if base_intrinsics:
            composite = sum(base_intrinsics) / len(base_intrinsics)
            if len(base_intrinsics) > 1:
                variance = sum((x - composite) ** 2 for x in base_intrinsics) / len(base_intrinsics)
                sigma = math.sqrt(variance)
                # Normalised agreement score: std-dev / current_price
                # 0.0 = perfect agreement; ~0.5+ = high dispersion
                agreement = sigma / current_price if current_price > 0 else None
                band = (composite - sigma, composite + sigma)
            else:
                # Single model: agreement is trivially perfect, band collapses
                agreement = 0.0
                band = (composite, composite)

            upside = (composite / current_price - 1.0) if current_price > 0 else None

        # Build human-readable note
        if not base_intrinsics:
            note = (
                f"No intrinsic model could run for {ticker}.  "
                "All valuation models were blocked by suitability checks.  "
                "Consider a P/S multiple if revenue is positive and growing."
            )
        else:
            n_models = len(base_intrinsics)
            composite_str = f"${composite:,.2f}" if composite is not None else "N/A"
            upside_str    = f"{upside:+.1%}" if upside is not None else "N/A"
            status = (
                "undervalued" if upside is not None and upside > 0.10
                else "overvalued" if upside is not None and upside < -0.10
                else "fairly valued"
            )
            note = (
                f"{n_models} model(s) ran for {ticker}.  "
                f"Composite Base intrinsic: {composite_str} "
                f"(implied upside: {upside_str}).  "
                f"Composite assessment: {status}."
            )
            if agreement is not None and agreement > 0.40:
                note += (
                    f"  Model agreement is LOW (score={agreement:.2f}) — "
                    "wide dispersion between model outputs; interpret with caution."
                )

        return cls(
            ticker=ticker,
            current_price=current_price,
            rows=rows,
            composite_intrinsic=composite,
            model_agreement_score=agreement,
            confidence_band=band,
            implied_upside=upside,
            models_run=models_run,
            models_skipped=models_skipped,
            note=note,
        )