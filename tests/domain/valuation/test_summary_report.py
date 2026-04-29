from __future__ import annotations

from dataclasses import dataclass
import json
import math
from types import SimpleNamespace

import pytest
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

class TestValuationSummaryReport:
    """
    valuation summary report behavior — ValuationSummaryReport.build() computes composite intrinsic,
    model_agreement_score, confidence_band, and implied_upside from
    per-model Base scenario rows.
    """

    def _make_row(self, model, scenario, iv, status="undervalued", price=100.0):
        from domain.valuation.models.summary import ModelScenarioRow
        return ModelScenarioRow(
            model_name=model,
            scenario=scenario,
            intrinsic_value=iv,
            valuation_status=status,
            implied_upside=(iv / price - 1.0),
        )

    def test_composite_is_equal_weight_average_of_base_ivs(self):
        """composite_intrinsic = mean of all Base scenario intrinsic values."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [
            self._make_row("DCF", "Base", 200.0),
            self._make_row("PE",  "Base", 300.0),
            self._make_row("ROE", "Base", 100.0),
            # Bear / Bull should NOT enter composite
            self._make_row("DCF", "Bear", 50.0),
            self._make_row("DCF", "Bull", 400.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF", "PE", "ROE"], models_skipped=[],
        )
        assert report.composite_intrinsic == pytest.approx(200.0)

    def test_model_agreement_score_is_normalised_std_dev(self):
        """agreement_score = std_dev(base_IVs) / current_price."""
        from domain.valuation.models.summary import ValuationSummaryReport
        ivs = [200.0, 300.0, 100.0]
        rows = [self._make_row("M1", "Base", ivs[0]),
                self._make_row("M2", "Base", ivs[1]),
                self._make_row("M3", "Base", ivs[2])]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["M1","M2","M3"], models_skipped=[],
        )
        mean  = sum(ivs) / 3
        sigma = math.sqrt(sum((x - mean) ** 2 for x in ivs) / 3)
        expected_score = sigma / 150.0
        assert report.model_agreement_score == pytest.approx(expected_score, rel=1e-6)

    def test_confidence_band_is_composite_plus_minus_sigma(self):
        """confidence_band = (composite − σ, composite + σ)."""
        from domain.valuation.models.summary import ValuationSummaryReport
        ivs = [200.0, 300.0]
        rows = [self._make_row("M1", "Base", ivs[0]),
                self._make_row("M2", "Base", ivs[1])]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["M1","M2"], models_skipped=[],
        )
        mean  = 250.0
        sigma = math.sqrt(((200 - 250)**2 + (300 - 250)**2) / 2)
        assert report.confidence_band == pytest.approx((mean - sigma, mean + sigma), rel=1e-6)

    def test_implied_upside_sign(self):
        """Positive implied_upside when composite > current_price."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 200.0, price=100.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=100.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.implied_upside == pytest.approx(1.0)  # 100% upside

    def test_no_models_ran_note_contains_guidance(self):
        """When all models are blocked, note must explain and suggest P/S."""
        from domain.valuation.models.summary import ValuationSummaryReport
        report = ValuationSummaryReport.build(
            ticker="AI", current_price=8.97,
            rows=[], models_run=[], models_skipped=["DCF", "PE", "ROE"],
        )
        assert report.composite_intrinsic is None
        assert "P/S" in report.note or "revenue" in report.note.lower(), (
            f"Note should mention P/S model.  Got: {report.note}"
        )
        assert "AI" in report.note

    def test_single_model_agreement_is_zero(self):
        """Single model → perfect agreement score = 0.0."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 300.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.model_agreement_score == 0.0

    def test_models_run_and_skipped_recorded(self):
        """models_run and models_skipped must be stored exactly as passed."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [self._make_row("DCF", "Base", 200.0)]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows,
            models_run=["DCF"],
            models_skipped=["PE", "ROE"],
        )
        assert report.models_run    == ["DCF"]
        assert report.models_skipped == ["PE", "ROE"]

    def test_bear_bull_rows_excluded_from_composite(self):
        """Bear and Bull rows must not contribute to composite_intrinsic."""
        from domain.valuation.models.summary import ValuationSummaryReport
        rows = [
            self._make_row("DCF", "Bear", 50.0),
            self._make_row("DCF", "Base", 200.0),
            self._make_row("DCF", "Bull", 400.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=150.0,
            rows=rows, models_run=["DCF"], models_skipped=[],
        )
        assert report.composite_intrinsic == pytest.approx(200.0)

    def test_note_mentions_high_dispersion_when_agreement_low(self):
        """When agreement > 0.40, note should warn about low model agreement."""
        from domain.valuation.models.summary import ValuationSummaryReport
        # Widely spread Base IVs → high agreement score
        rows = [
            self._make_row("M1", "Base", 50.0,   price=100.0),
            self._make_row("M2", "Base", 500.0,  price=100.0),
        ]
        report = ValuationSummaryReport.build(
            ticker="TEST", current_price=100.0,
            rows=rows, models_run=["M1","M2"], models_skipped=[],
        )
        assert report.model_agreement_score > 0.40
        assert "LOW" in report.note or "low" in report.note.lower() or "agreement" in report.note.lower()
