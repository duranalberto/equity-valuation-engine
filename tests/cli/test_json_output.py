from __future__ import annotations

from dataclasses import dataclass
import json
import math
from types import SimpleNamespace

import pytest
from tests.unit.fixtures import make_adbe_metrics, make_ai_metrics, make_orcl_metrics

@dataclass
class _FakeScenarioResult:
    growth_rates: list[float]
    valuation_status: str
    intrinsic_value_per_share: float

@dataclass
class _FakeValuationReport:
    scenarios: dict[str, _FakeScenarioResult]

class _FakeManagerBase:
    score = 0
    suitable = True
    interpretation = "Suitable"
    error: Exception | None = None

    def __init__(self, stock_metrics):
        self.stock_metrics = stock_metrics

    def validate_metrics(self, registry=None):
        from domain.valuation.policies import ValuationCheckResult
        return ValuationCheckResult(
            ticker=self.stock_metrics.profile.ticker,
            is_suitable=self.suitable,
            total_severity_score=self.score,
            interpretation=self.interpretation,
            factors=[],
        )

    def execute_valuation_scenarios(self):
        if self.error is not None:
            raise self.error
        return _FakeValuationReport(
            scenarios={
                "Base": _FakeScenarioResult(
                    growth_rates=[0.10],
                    valuation_status="undervalued",
                    intrinsic_value_per_share=150.0,
                )
            }
        )

class DCFManager(_FakeManagerBase):
    pass

class PEManager(_FakeManagerBase):
    score = 99
    suitable = False
    interpretation = "PE blocked by suitability"

class ROEManager(_FakeManagerBase):
    error = RuntimeError("valuation exploded")

class TestCliCoherentJsonOutput:
    def _run_json(self, monkeypatch, capsys):
        return self._run_cli(monkeypatch, capsys, print_cli=False)

    def _run_cli(self, monkeypatch, capsys, *, print_cli):
        import cli.main as cli_main
        from domain.core.missing import MissingReason
        from domain.core.missing_registry import MissingValueRegistry

        metrics = make_orcl_metrics()
        registry = MissingValueRegistry()
        registry.record(
            "Financials",
            "revenue_ttm",
            MissingReason.NOT_IN_SOURCE,
            "not present in source",
        )
        monkeypatch.setattr(
            cli_main,
            "fetch_stock_metrics",
            lambda ticker: (metrics, registry),
        )

        cli_main.run_for_ticker(
            cli_main.RunConfig(ticker="TEST", print_cli=print_cli, print_json=True),
            managers=[DCFManager, PEManager, ROEManager],
        )

        return capsys.readouterr().out

    def test_json_mode_prints_one_parseable_object(self, monkeypatch, capsys):
        stdout = self._run_json(monkeypatch, capsys)

        payload = json.loads(stdout)

        assert set(payload) >= {
            "ticker",
            "stock_metrics",
            "missing_data",
            "suitability",
            "valuations",
            "skipped_models",
            "summary",
        }
        assert payload["ticker"] == "TEST"
        assert set(payload["valuations"]) == {"DCF"}
        assert set(payload["suitability"]) == {"DCF", "PE", "ROE"}
        assert payload["summary"]["models_run"] == ["DCF"]
        assert payload["summary"]["models_skipped"] == ["PE", "ROE"]

    def test_json_mode_omits_legacy_section_headers(self, monkeypatch, capsys):
        stdout = self._run_json(monkeypatch, capsys)

        assert "--- Stock Metrics JSON ---" not in stdout
        assert "--- DCF Result JSON ---" not in stdout
        assert "--- Summary JSON ---" not in stdout
        assert stdout.strip().startswith("{")
        assert stdout.strip().endswith("}")

    def test_json_payload_includes_missing_and_skipped_details(self, monkeypatch, capsys):
        payload = json.loads(self._run_json(monkeypatch, capsys))

        assert payload["missing_data"]["count"] == 1
        assert payload["missing_data"]["summary"] == {
            "Financials": ["revenue_ttm"],
        }
        assert payload["missing_data"]["entries"][0]["reason"] == "not_in_source"

        pe_skip = payload["skipped_models"]["PE"]
        assert pe_skip["reason"] == "PE blocked by suitability"
        assert pe_skip["total_severity_score"] == 99
        assert pe_skip["is_suitable"] is False
        assert pe_skip["error"] is None

        roe_skip = payload["skipped_models"]["ROE"]
        assert roe_skip["reason"] == "valuation exploded"
        assert roe_skip["error"] == "valuation exploded"

    def test_all_mode_prints_final_labeled_json_block(self, monkeypatch, capsys):
        stdout = self._run_cli(monkeypatch, capsys, print_cli=True)
        lines = [line for line in stdout.splitlines() if line]

        assert "--- JSON Result ---" in lines
        marker_index = lines.index("--- JSON Result ---")
        payload = json.loads(lines[marker_index + 1])
        assert payload["ticker"] == "TEST"
        assert payload["summary"]["models_run"] == ["DCF"]
