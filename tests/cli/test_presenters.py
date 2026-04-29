from __future__ import annotations

import logging

from domain.core.missing_registry import MissingValueRegistry
from tests.unit.fixtures import make_orcl_metrics


def test_ev_ebitda_presenter_renders_scenarios(capsys) -> None:
    from application.valuations.ev_ebitda.valuation import execute_ev_ebitda_scenarios
    from cli.presenters.ev_ebitda_presenter import cli_print_valuation

    metrics = make_orcl_metrics()
    cli_print_valuation(metrics, execute_ev_ebitda_scenarios(metrics))

    output = capsys.readouterr().out
    assert "EV/EBITDA Valuation" in output
    assert "Bear" in output
    assert "Base" in output
    assert "Bull" in output
    assert "Intrinsic EV" in output


def test_ps_presenter_renders_scenarios(capsys) -> None:
    from application.valuations.ps.valuation import execute_ps_scenarios
    from cli.presenters.ps_presenter import cli_print_valuation

    metrics = make_orcl_metrics()
    cli_print_valuation(metrics, execute_ps_scenarios(metrics))

    output = capsys.readouterr().out
    assert "P/S Valuation" in output
    assert "Bear" in output
    assert "Base" in output
    assert "Bull" in output
    assert "Intrinsic Market Cap" in output


def test_ddm_presenter_renders_scenarios(capsys) -> None:
    from application.valuations.ddm.valuation import execute_ddm_scenarios
    from cli.presenters.ddm_presenter import cli_print_valuation

    metrics = make_orcl_metrics()
    cli_print_valuation(metrics, execute_ddm_scenarios(metrics))

    output = capsys.readouterr().out
    assert "DDM Valuation" in output
    assert "Bear" in output
    assert "Base" in output
    assert "Bull" in output
    assert "Implied Return" in output
    assert "Implied Div Yield" in output


def test_nav_presenter_renders_scenarios(capsys) -> None:
    from application.valuations.nav.valuation import execute_nav_scenarios
    from cli.presenters.nav_presenter import cli_print_valuation

    metrics = make_orcl_metrics()
    cli_print_valuation(metrics, execute_nav_scenarios(metrics))

    output = capsys.readouterr().out
    assert "NAV Valuation" in output
    assert "Bear" in output
    assert "Base" in output
    assert "Bull" in output
    assert "Price/NAV" in output
    assert "Intangible %" in output


def test_reverse_dcf_presenter_renders_diagnostics(capsys) -> None:
    from application.valuations.reverse_dcf.valuation import solve_reverse_dcf
    from cli.presenters.reverse_dcf_presenter import cli_print_valuation

    metrics = make_orcl_metrics()
    cli_print_valuation(metrics, solve_reverse_dcf(metrics))

    output = capsys.readouterr().out
    assert "Reverse DCF Diagnostics" in output
    assert "Implied Growth Rate" in output
    assert "WACC" in output
    assert "Terminal Growth Rate" in output
    assert "Verification Error" in output
    assert "Interpretation:" in output


def _run_cli(monkeypatch, caplog, metrics, managers):
    import cli.main as cli_main

    monkeypatch.setattr(
        cli_main,
        "fetch_stock_metrics",
        lambda ticker: (metrics, MissingValueRegistry()),
    )

    with caplog.at_level(logging.WARNING, logger="cli.main"):
        cli_main.run_for_ticker(
            cli_main.RunConfig(ticker=metrics.profile.ticker, print_cli=True, print_json=False),
            managers=managers,
        )


def test_default_cli_run_has_no_missing_intrinsic_model_presenter_warning(monkeypatch, caplog, capsys) -> None:
    import cli.main as cli_main

    _run_cli(monkeypatch, caplog, make_orcl_metrics(), cli_main.VALUATION_MANAGERS)
    capsys.readouterr()

    assert not any(
        "No CLI presenter registered" in record.message for record in caplog.records
    )


def test_reverse_dcf_cli_run_has_no_missing_presenter_warning(monkeypatch, caplog, capsys) -> None:
    import cli.main as cli_main
    from application import ReverseDCFManager

    _run_cli(
        monkeypatch,
        caplog,
        make_orcl_metrics(),
        [*cli_main.VALUATION_MANAGERS, ReverseDCFManager],
    )
    capsys.readouterr()

    assert not any(
        "No CLI presenter registered" in record.message for record in caplog.records
    )
