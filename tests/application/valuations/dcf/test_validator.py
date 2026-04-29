"""
Tests for DCF validator normalized FCF handling:
  DCFChecker._check_free_cash_flow() must NOT hard-block (score=99) when
  capex_spike_detected=True AND normalised_fcf > 0, even though raw fcf_ttm
  and last_year_fcf are both negative.
"""
import pytest

from tests.unit.fixtures import make_orcl_metrics, make_ai_metrics, make_adbe_metrics
from domain.metrics.stock import Valuation


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run_checker(metrics):
    """Import and run DCFChecker against the supplied metrics stub."""
    # We import here (not at module level) so path-bootstrap above takes effect.
    from application.valuations.dcf.validator import DCFChecker
    checker = DCFChecker(metrics)
    return checker.evaluate()


def _clone_valuation(v: Valuation, **overrides) -> Valuation:
    import dataclasses
    return dataclasses.replace(v, **overrides)


# Normalized FCF substitution

class TestDCFValidatorNormalizedFCFSubstitution:
    """ORCL profile: capex spike + positive normalised FCF."""

    def test_is_suitable_true(self):
        """Validator must NOT block when normalised FCF is available and positive."""
        result = _run_checker(make_orcl_metrics())
        assert result.is_suitable is True, (
            f"Expected is_suitable=True for ORCL (normalised FCF available) "
            f"but got is_suitable={result.is_suitable}.  "
            f"Score={result.total_severity_score}, "
            f"interpretation='{result.interpretation}'"
        )

    def test_score_below_hard_block(self):
        """Score must be strictly below the 99 hard-block sentinel."""
        result = _run_checker(make_orcl_metrics())
        assert result.total_severity_score < 99, (
            f"Score={result.total_severity_score} should be < 99 for ORCL "
            f"(normalised FCF available)."
        )

    def test_warning_factor_emitted(self):
        """A WARNING factor describing the normalised-seed substitution must be present."""
        result = _run_checker(make_orcl_metrics())
        from domain.valuation.policies import FactorSeverity
        warning_names = [f.name for f in result.factors if f.severity == FactorSeverity.WARNING]
        assert any("Normalised" in n or "Negative Raw FCF" in n for n in warning_names), (
            f"Expected a WARNING factor mentioning normalised FCF substitution. "
            f"Got factors: {[f.name for f in result.factors]}"
        )

    def test_no_dual_negative_critical_factor(self):
        """The 'Dual Negative FCF — DCF Invalid' CRITICAL factor must NOT appear."""
        result = _run_checker(make_orcl_metrics())
        critical_names = [f.name for f in result.factors]
        assert "Dual Negative FCF — DCF Invalid" not in critical_names, (
            f"Hard-block factor should not be emitted when normalised FCF is available. "
            f"Got factors: {critical_names}"
        )

    def test_normalised_fcf_value_in_message(self):
        """The WARNING factor message must mention the normalised FCF value."""
        result = _run_checker(make_orcl_metrics())
        from domain.valuation.policies import FactorSeverity
        warning_messages = [f.message for f in result.factors if f.severity == FactorSeverity.WARNING]
        # normalised_fcf = 16.648B → should mention "16." somewhere
        assert any("16." in m for m in warning_messages), (
            f"Expected normalised FCF amount (~16.6B) mentioned in a WARNING message. "
            f"WARNING messages: {warning_messages}"
        )


# Dual-negative FCF behavior

class TestDCFValidatorDualNegativeFCF:
    """C3.ai profile: dual negative, no normalised FCF → still blocks."""

    def test_is_suitable_false(self):
        """C3.ai has no normalised FCF; dual-negative hard-block must still fire."""
        result = _run_checker(make_ai_metrics())
        assert result.is_suitable is False, (
            f"Expected is_suitable=False for AI (no normalised FCF) "
            f"but got is_suitable={result.is_suitable}."
        )

    def test_score_is_99(self):
        """Hard-block sentinel (99) must be assigned."""
        result = _run_checker(make_ai_metrics())
        assert result.total_severity_score == 99, (
            f"Expected score=99 for AI dual-negative, got {result.total_severity_score}."
        )

    def test_dual_negative_factor_present(self):
        """The hard-block 'Dual Negative FCF' CRITICAL factor must be emitted."""
        result = _run_checker(make_ai_metrics())
        names = [f.name for f in result.factors]
        assert "Dual Negative FCF — DCF Invalid" in names, (
            f"Expected 'Dual Negative FCF — DCF Invalid' factor.  Got: {names}"
        )


# FCF edge cases

class TestDCFValidatorFCFEdgeCases:
    """Additional edge cases around the normalised FCF substitution gate."""

    def _orcl_with_overrides(self, **val_overrides):
        m = make_orcl_metrics()
        import dataclasses
        m.valuation = dataclasses.replace(m.valuation, **val_overrides)
        return m

    def test_capex_spike_but_negative_normalised_fcf_still_blocks(self):
        """
        capex_spike_detected=True but normalised_fcf < 0 must still hard-block.
        Normalised FCF being negative means the business burns cash even at
        normal capex — DCF is still invalid.
        """
        m = self._orcl_with_overrides(normalized_fcf=-500_000_000.0)
        result = _run_checker(m)
        assert result.is_suitable is False
        assert result.total_severity_score == 99

    def test_capex_spike_but_normalised_fcf_none_still_blocks(self):
        """normalised_fcf=None (couldn't compute) with dual-negative → block."""
        m = self._orcl_with_overrides(normalized_fcf=None)
        result = _run_checker(m)
        assert result.is_suitable is False
        assert result.total_severity_score == 99

    def test_capex_spike_false_dual_negative_blocks_normally(self):
        """No spike, both FCFs negative → hard-block regardless."""
        m = self._orcl_with_overrides(
            capex_spike_detected=False,
            normalized_fcf=None,
        )
        result = _run_checker(m)
        assert result.is_suitable is False
        assert result.total_severity_score == 99

    def test_both_fcf_positive_no_spike_passes_cleanly(self):
        """
        When both FCFs are positive and there is no spike, no FCF-related
        factors should be added at all (existing happy-path preserved).
        """
        m = make_adbe_metrics()
        result = _run_checker(m)
        # ADBE FCFs are positive — no FCF factors expected
        fcf_factor_names = [f.name for f in result.factors if "FCF" in f.name]
        assert not fcf_factor_names, (
            f"No FCF factors expected for ADBE (positive FCF), got: {fcf_factor_names}"
        )


from types import SimpleNamespace

from application.valuations.dcf.validator import evaluate_dcf

def _make_minimal_stock_metrics(
    *,
    fcf_ttm: float,
    last_year_fcf: float,
    capex_spike_detected: bool = False,
    normalized_fcf: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        profile=SimpleNamespace(ticker="TEST", sector=None),
        cash_flow=SimpleNamespace(
            fcf_ttm=fcf_ttm,
            last_year_fcf=last_year_fcf,
            last_quarter_fcf=1.0,
            operating_cf_ttm=20.0,
        ),
        financials=SimpleNamespace(
            net_income_ttm=100.0,
            revenue_growth_rate=0.1,
        ),
        valuation=SimpleNamespace(
            capex_spike_detected=capex_spike_detected,
            normalized_fcf=normalized_fcf,
            cost_of_debt=0.05,
            corporate_tax_rate=0.2,
        ),
        balance_sheet=SimpleNamespace(
            total_debt=10.0,
            cash_and_equivalents=5.0,
            total_equity=20.0,
        ),
        market_data=SimpleNamespace(
            market_cap=100.0,
            beta=1.0,
            shares_outstanding=10.0,
            current_price=1.0,
            eps_ttm=1.0,
            pe_ttm=10.0,
        ),
    )

def test_dcf_validator_allows_capex_spike_when_normalized_fcf_exists() -> None:
    stock_metrics = _make_minimal_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=8.0,
        capex_spike_detected=True,
        normalized_fcf=25.0,
    )

    result = evaluate_dcf(stock_metrics)

    assert result.is_suitable is True
    assert result.total_severity_score < 99
    assert any(f.name == "Capex Spike Detected" for f in result.factors)

def test_dcf_validator_blocks_dual_negative_fcf_without_normalization() -> None:
    stock_metrics = _make_minimal_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=-8.0,
        capex_spike_detected=True,
        normalized_fcf=None,
    )

    result = evaluate_dcf(stock_metrics)

    assert result.is_suitable is False
    assert result.total_severity_score == 99
