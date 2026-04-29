from __future__ import annotations

import json
import sys
from dataclasses import replace

from domain.core.missing_registry import MissingValueRegistry
from tests.unit.fixtures import make_ai_metrics, make_orcl_metrics


def _run_json(monkeypatch, capsys, metrics, managers):
    import cli.main as cli_main

    monkeypatch.setattr(
        cli_main,
        "fetch_stock_metrics",
        lambda ticker: (metrics, MissingValueRegistry()),
    )

    cli_main.run_for_ticker(
        cli_main.RunConfig(ticker=metrics.profile.ticker, print_cli=False, print_json=True),
        managers=managers,
    )

    return json.loads(capsys.readouterr().out)


def test_default_cli_managers_include_intrinsic_models() -> None:
    import cli.main as cli_main

    model_names = [manager.__name__.replace("Manager", "") for manager in cli_main.VALUATION_MANAGERS]

    assert model_names == ["DCF", "PE", "ROE", "EVEBITDA", "PS", "DDM", "NAV"]


def test_default_json_run_includes_intrinsic_reports(monkeypatch, capsys) -> None:
    import cli.main as cli_main

    payload = _run_json(
        monkeypatch,
        capsys,
        make_orcl_metrics(),
        cli_main.VALUATION_MANAGERS,
    )

    expected_models = {"DCF", "PE", "ROE", "EVEBITDA", "PS", "DDM", "NAV"}
    assert set(payload["valuations"]) == expected_models
    assert set(payload["suitability"]) == expected_models
    assert payload["skipped_models"] == {}

    row_models = {row["model_name"] for row in payload["summary"]["rows"]}
    assert expected_models <= row_models
    assert len(payload["summary"]["rows"]) == 21
    assert payload["valuations"]["DDM"]["dividend_growth_rate"] == 0.03


def test_ai_style_company_can_run_ps_when_revenue_growth_is_positive(monkeypatch, capsys) -> None:
    import cli.main as cli_main
    from application import PSManager

    metrics = make_ai_metrics()
    metrics.financials = replace(metrics.financials, revenue_growth_rate=0.12)

    payload = _run_json(monkeypatch, capsys, metrics, [PSManager])

    assert set(payload["valuations"]) == {"PS"}
    assert payload["summary"]["models_run"] == ["PS"]
    assert payload["skipped_models"] == {}


def test_reverse_dcf_parse_flag_is_explicit(monkeypatch) -> None:
    import cli.main as cli_main

    monkeypatch.setattr(
        sys,
        "argv",
        ["valuation-engine", "ORCL", "--json", "--reverse-dcf"],
    )

    config = cli_main.parse_arguments()

    assert config.ticker == "ORCL"
    assert config.print_json is True
    assert config.include_reverse_dcf is True


def test_reverse_dcf_is_json_visible_but_excluded_from_composite(monkeypatch, capsys) -> None:
    import cli.main as cli_main
    from application import ReverseDCFManager

    metrics = make_orcl_metrics()
    default_payload = _run_json(
        monkeypatch,
        capsys,
        metrics,
        cli_main.VALUATION_MANAGERS,
    )
    reverse_payload = _run_json(
        monkeypatch,
        capsys,
        metrics,
        [*cli_main.VALUATION_MANAGERS, ReverseDCFManager],
    )

    assert "ReverseDCF" not in default_payload["valuations"]
    assert "ReverseDCF" in reverse_payload["valuations"]
    assert reverse_payload["valuations"]["ReverseDCF"]["result"]["implied_growth_rate"] is not None

    reverse_row_models = {
        row["model_name"] for row in reverse_payload["summary"]["rows"]
    }
    assert "ReverseDCF" not in reverse_row_models
    assert reverse_payload["summary"]["composite_intrinsic"] == (
        default_payload["summary"]["composite_intrinsic"]
    )


def test_intrinsic_model_skipped_models_are_listed_with_reasons(monkeypatch, capsys) -> None:
    from application import DDMManager, EVEBITDAManager, PSManager, ReverseDCFManager

    payload = _run_json(
        monkeypatch,
        capsys,
        make_ai_metrics(),
        [EVEBITDAManager, PSManager, DDMManager, ReverseDCFManager],
    )

    assert payload["valuations"] == {}
    assert set(payload["skipped_models"]) == {"EVEBITDA", "PS", "DDM", "ReverseDCF"}
    assert payload["skipped_models"]["EVEBITDA"]["total_severity_score"] == 99
    assert payload["skipped_models"]["PS"]["reason"] == (
        "P/S valuation blocked: revenue is declining."
    )
    assert payload["skipped_models"]["DDM"]["is_suitable"] is False
    assert payload["skipped_models"]["ReverseDCF"]["error"] is None
