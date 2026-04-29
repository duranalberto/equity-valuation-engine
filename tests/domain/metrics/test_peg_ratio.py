from __future__ import annotations

from dataclasses import dataclass
import json
import math
from types import SimpleNamespace

import pytest
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

class TestPegRatioGrowthSource:
    """
    PEG growth-source handling — Ratios.build() now uses forward_growth_rate as the primary PEG
    denominator instead of TTM net_income_growth.

    This fixes artificially high PEG values: ORCL 54x, ADBE 48x — artefacts
    of volatile TTM NI growth being used instead of the forward CAGR.
    """

    def _build_ratios(self, metrics):
        """Import and run Ratios.build() on the given metrics stub."""
        from domain.metrics.stock import Ratios
        ratios, _ = Ratios.build(
            financials=metrics.financials,
            cash_flow=metrics.cash_flow,
            balance_sheet=metrics.balance_sheet,
            market_data=metrics.market_data,
            valuation=metrics.valuation,
        )
        return ratios

    def test_peg_source_is_forward_ni_cagr_when_available(self):
        """
        When forward_growth_rate is non-zero, peg_growth_source must be
        'forward_ni_cagr' — not 'ttm_ni_growth'.
        """
        ratios = self._build_ratios(make_adbe_metrics())
        assert ratios.peg_growth_source == "forward_ni_cagr", (
            f"ADBE: expected peg_growth_source='forward_ni_cagr', "
            f"got '{ratios.peg_growth_source}'."
        )

    def test_peg_uses_forward_growth_rate_denominator(self):
        """
        PEG = pe_ttm / forward_growth_rate (not net_income_growth).
        ADBE: pe_ttm=14.1642, forward_growth_rate=0.1445
        Expected PEG ≈ 14.1642 / 0.1445 ≈ 98.0 (not the old 47.79).
        """
        adbe = make_adbe_metrics()
        ratios = self._build_ratios(adbe)
        expected = adbe.market_data.pe_ttm / adbe.valuation.forward_growth_rate
        assert abs(ratios.peg_ratio - expected) < 0.01, (
            f"ADBE PEG ratio={ratios.peg_ratio:.4f}, expected {expected:.4f} "
            f"(pe_ttm / forward_growth_rate)."
        )

    def test_peg_falls_back_to_ttm_growth_when_forward_rate_zero(self):
        """
        When forward_growth_rate=0.0, must fall back to net_income_growth
        and set peg_growth_source='ttm_ni_growth'.
        """
        adbe = make_adbe_metrics()
        # Zero out forward_growth_rate to force fallback
        adbe.valuation = SimpleNamespace(
            **{**vars(adbe.valuation), "forward_growth_rate": 0.0}
        )
        ratios = self._build_ratios(adbe)
        assert ratios.peg_growth_source == "ttm_ni_growth", (
            f"Expected fallback to 'ttm_ni_growth' when forward_growth_rate=0.  "
            f"Got '{ratios.peg_growth_source}'."
        )
        expected = adbe.market_data.pe_ttm / adbe.financials.net_income_growth
        assert abs(ratios.peg_ratio - expected) < 0.01

    def test_peg_is_zero_when_no_pe_available(self):
        """When pe_ttm is None (negative EPS company), PEG must remain 0."""
        ratios = self._build_ratios(make_ai_metrics())
        assert ratios.peg_ratio == 0.0, (
            f"AI has no P/E (negative EPS), PEG should be 0.  Got {ratios.peg_ratio}."
        )

    def test_orcl_peg_uses_forward_growth_rate(self):
        """ORCL: pe_ttm=29.80, forward_growth_rate=0.2281 → PEG ≈ 130.6"""
        orcl   = make_orcl_metrics()
        ratios = self._build_ratios(orcl)
        expected = orcl.market_data.pe_ttm / orcl.valuation.forward_growth_rate
        assert abs(ratios.peg_ratio - expected) < 0.01, (
            f"ORCL PEG={ratios.peg_ratio:.4f}, expected {expected:.4f}."
        )
        # New PEG should be meaningfully different from old TTM-based 54.30
        assert abs(ratios.peg_ratio - 54.30) > 5.0, (
            "ORCL PEG looks like it's still using TTM NI growth denominator."
        )
