"""
Tests for BUG-D and BUG-G fixes in application/valuations/utils.py.

BUG-D: _derive_base_growth() must emit logger.warning (and in
       generate_growth_scenarios() scenarios that hit the ceiling/floor)
       when growth rates are clamped.

BUG-G: _derive_base_growth() must disqualify net_income_growth when
       net_income_ttm is negative, even if the ratio of two negatives
       produces a large-looking positive number (+55% for C3.ai).
"""
import logging
import pytest
import dataclasses

from tests.unit.fixtures import make_ai_metrics, make_orcl_metrics, make_adbe_metrics


def _derive(metrics):
    from application.valuations.utils import _derive_base_growth
    return _derive_base_growth(metrics)


def _generate_scenarios(metrics, years=10, margin=0.25):
    from application.valuations.utils import generate_growth_scenarios
    return generate_growth_scenarios(metrics, years, margin)


# ── BUG-G Tests ───────────────────────────────────────────────────────────────

class TestBugG_NegativeIncomeGrowthDisqualified:
    """
    UT-G1 — C3.ai: net_income_ttm < 0 must disqualify net_income_growth signal.

    C3.ai data:
      net_income_ttm      = -434_502_000   (NEGATIVE)
      net_income_growth   = +55.35%        (ratio of two negatives — meaningless)
      revenue_growth_rate = -1.03%         (slightly negative)
      forward_growth_rate = 14.55%         (suspect — from NI CAGR of negatives)

    After BUG-G fix:
      net_income_growth MUST be skipped.
      forward_growth_rate should be the primary signal (if non-zero and finite).
    """

    def test_net_income_growth_not_used_when_income_negative(self):
        """
        _derive_base_growth() must NOT return net_income_growth (55.35%) for C3.ai.
        Even though it is the largest positive signal, it is derived from two
        negative numbers and is not economically meaningful.
        """
        m = make_ai_metrics()
        # Temporarily zero out forward_growth_rate and fcf_cagr so the test
        # can verify the NI growth signal specifically gets skipped.
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should NOT be the raw 55.35% net_income_growth value
        assert abs(result - m.financials.net_income_growth) > 0.01, (
            f"_derive_base_growth() returned {result:.4f} which matches "
            f"net_income_growth ({m.financials.net_income_growth:.4f}).  "
            f"This signal should have been disqualified (net_income_ttm < 0)."
        )

    def test_fallback_to_revenue_growth_when_ni_negative(self):
        """
        With forward_growth_rate=0 and fcf_cagr=0 and NI disqualified,
        the engine should fall through to revenue_growth_rate.

        C3.ai revenue_growth_rate = -1.03% (negative but valid as a signal).
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should be clamped revenue_growth_rate = -0.0103
        expected = m.financials.revenue_growth_rate
        assert abs(result - expected) < 1e-6, (
            f"Expected fallback to revenue_growth_rate ({expected:.4f}), "
            f"got {result:.4f}."
        )

    def test_fallback_to_constant_when_all_signals_invalid(self):
        """
        When all signals are zero/disqualified, must fall back to
        _FALLBACK_BASE_GROWTH (0.04).
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            revenue_growth_rate=0.0,
            net_income_growth=0.5535,   # still present but should be disqualified
        )
        result = _derive(m)
        from application.valuations.utils import _FALLBACK_BASE_GROWTH
        assert abs(result - _FALLBACK_BASE_GROWTH) < 1e-6, (
            f"Expected fallback growth {_FALLBACK_BASE_GROWTH}, got {result:.4f}."
        )

    def test_positive_net_income_allows_ni_growth_signal(self):
        """
        When net_income_ttm > 0, net_income_growth IS a valid signal and
        should be used (with all higher-priority signals zeroed).
        This verifies BUG-G fix does not over-block.
        """
        m = make_ai_metrics()
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            net_income_ttm=100_000_000.0,       # positive — signal now valid
            net_income_growth=0.30,
        )
        result = _derive(m)
        assert abs(result - 0.30) < 1e-6, (
            f"Expected net_income_growth (0.30) to be used when "
            f"net_income_ttm > 0.  Got {result:.4f}."
        )

    def test_profitable_company_unaffected(self):
        """
        ORCL net_income_ttm = +$16.2B — net_income_growth signal should
        remain fully available (existing behaviour for profitable companies).
        """
        m = make_orcl_metrics()
        # Zero higher-priority signals to isolate NI growth
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        result = _derive(m)
        # Should fall to net_income_growth = 54.87%  → clamped to 50%
        from application.valuations.utils import _GROWTH_CEILING
        expected = min(m.financials.net_income_growth, _GROWTH_CEILING)
        assert abs(result - expected) < 1e-6, (
            f"ORCL (profitable): expected clamped NI growth {expected:.4f}, "
            f"got {result:.4f}."
        )


# ── BUG-D Tests ───────────────────────────────────────────────────────────────

class TestBugD_GrowthCeilingDiagnostic:
    """
    UT-D1 — Clipping at _GROWTH_CEILING must emit logger.warning.
    """

    def test_ceiling_clip_emits_warning_in_derive(self, caplog):
        """
        When raw growth exceeds 50%, _clamp_and_warn must log a WARNING.
        """
        m = make_orcl_metrics()
        # Set NI growth to 80% (above ceiling) and zero higher-priority signals
        m.valuation = dataclasses.replace(
            m.valuation,
            forward_growth_rate=0.0,
            fcf_cagr=0.0,
        )
        m.financials = dataclasses.replace(
            m.financials,
            net_income_ttm=100_000_000.0,   # positive so signal is valid
            net_income_growth=0.80,          # above 50% ceiling
        )
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _derive(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("clamped" in t.lower() or "ceiling" in t.lower() for t in warning_texts), (
            f"Expected a WARNING about growth ceiling clip.  "
            f"Got warnings: {warning_texts}"
        )

    def test_ceiling_clip_in_scenario_generator_emits_warning(self, caplog):
        """
        generate_growth_scenarios() must log a WARNING when the Bull scenario
        ceiling binds on at least one year.
        """
        m = make_orcl_metrics()
        # Force base_growth to 50% — Bull multiplier (1.25×) = 62.5% > ceiling
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=0.50)
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("ceiling" in t.lower() or "capped" in t.lower() for t in warning_texts), (
            f"Expected WARNING about scenario ceiling clip.  "
            f"Got warnings: {warning_texts}"
        )

    def test_no_clip_no_warning(self, caplog):
        """
        ADBE base growth ~14.45% — well below the 50% ceiling for all
        scenarios.  No clipping warning should be emitted.
        """
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(make_adbe_metrics())

        clip_warnings = [
            r.message for r in caplog.records
            if r.levelno == logging.WARNING and
            ("clamped" in r.message.lower() or "ceiling" in r.message.lower() or
             "floor" in r.message.lower())
        ]
        assert not clip_warnings, (
            f"Unexpected clipping warnings for ADBE: {clip_warnings}"
        )

    def test_floor_clip_emits_warning(self, caplog):
        """
        When growth goes below -20% floor, a WARNING must be emitted for
        the Bear scenario.
        """
        m = make_adbe_metrics()
        # Set forward_growth_rate to -0.30 so Bear scenario clips the floor
        m.valuation = dataclasses.replace(m.valuation, forward_growth_rate=-0.30)
        with caplog.at_level(logging.WARNING, logger="application.valuations.utils"):
            _generate_scenarios(m)

        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("floor" in t.lower() or "clamped" in t.lower() for t in warning_texts), (
            f"Expected WARNING about floor clip.  Got warnings: {warning_texts}"
        )


# ── Combined regression tests ─────────────────────────────────────────────────

class TestCombinedRegression:
    """Ensure BUG-D and BUG-G fixes don't break normal profitable-company paths."""

    def test_orcl_base_growth_uses_forward_rate(self):
        """ORCL forward_growth_rate = 22.81% should be the primary signal."""
        result = _derive(make_orcl_metrics())
        assert abs(result - 0.2281) < 1e-4, (
            f"ORCL base growth should equal forward_growth_rate (0.2281), got {result:.4f}."
        )

    def test_adbe_base_growth_uses_forward_rate(self):
        """ADBE forward_growth_rate = 14.45% should be the primary signal."""
        result = _derive(make_adbe_metrics())
        assert abs(result - 0.1445) < 1e-4, (
            f"ADBE base growth should equal forward_growth_rate (0.1445), got {result:.4f}."
        )

    def test_scenarios_generate_three_lists(self):
        """generate_growth_scenarios always returns Bear, Base, Bull keys."""
        for m in (make_orcl_metrics(), make_adbe_metrics()):
            scenarios = _generate_scenarios(m)
            assert set(scenarios.keys()) == {"Bear", "Base", "Bull"}

    def test_scenarios_have_correct_length(self):
        """Each scenario list must have exactly projection_years entries."""
        for years in (5, 10, 15):
            scenarios = _generate_scenarios(make_adbe_metrics(), years=years)
            for name, rates in scenarios.items():
                assert len(rates) == years, (
                    f"{name}: expected {years} rates, got {len(rates)}."
                )

    def test_bear_growth_lower_than_bull(self):
        """Bear mean growth should be lower than Bull mean growth."""
        for m in (make_orcl_metrics(), make_adbe_metrics()):
            scenarios = _generate_scenarios(m)
            bear_mean = sum(scenarios["Bear"]) / len(scenarios["Bear"])
            bull_mean = sum(scenarios["Bull"]) / len(scenarios["Bull"])
            assert bear_mean < bull_mean, (
                f"Bear mean ({bear_mean:.4f}) should be < Bull mean ({bull_mean:.4f})."
            )
