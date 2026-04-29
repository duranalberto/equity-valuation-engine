import argparse
import logging
import sys
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Type

from application import (
    DCFManager,
    DDMManager,
    EVEBITDAManager,
    MetricsLoader,
    NAVManager,
    PEManager,
    PSManager,
    ReverseDCFManager,
    ROEManager,
)
from cli.json_formatter import to_json
from domain import StockMetrics
from domain.core.missing_registry import MissingValueRegistry
from domain.valuation.models.summary import ModelScenarioRow, ValuationSummaryReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .presenters.dcf_presenter import cli_print_valuation as dcf_print
from .presenters.ddm_presenter import cli_print_valuation as ddm_print
from .presenters.ev_ebitda_presenter import cli_print_valuation as ev_ebitda_print
from .presenters.nav_presenter import cli_print_valuation as nav_print
from .presenters.pe_presenter import cli_print_valuation as pe_print
from .presenters.ps_presenter import cli_print_valuation as ps_print
from .presenters.reverse_dcf_presenter import cli_print_valuation as reverse_dcf_print
from .presenters.roe_presenter import cli_print_valuation as roe_print
from .presenters.summary_presenter import cli_print_summary


class RunConfig(NamedTuple):
    ticker:              str
    print_cli:           bool
    print_json:          bool
    include_reverse_dcf: bool = False


class ModelRunOutcome(NamedTuple):
    model_name:          str
    suitability_result:  ValuationCheckResult
    valuation_report:    Optional[object]
    was_skipped:         bool
    error:               Optional[str] = None


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALUATION_MANAGERS: List[Type[ValuationManager]] = [
    DCFManager,
    PEManager,
    ROEManager,
    EVEBITDAManager,
    PSManager,
    DDMManager,
    NAVManager,
]

CLI_PRESENTERS: Dict[Type[ValuationManager], Callable] = {
    DCFManager:        dcf_print,
    PEManager:         pe_print,
    ROEManager:        roe_print,
    EVEBITDAManager:   ev_ebitda_print,
    PSManager:         ps_print,
    DDMManager:        ddm_print,
    NAVManager:        nav_print,
    ReverseDCFManager: reverse_dcf_print,
}

_VALUATION_SKIP_THRESHOLD = 6


def fetch_stock_metrics(ticker: str) -> Tuple[StockMetrics, MissingValueRegistry]:
    registry = MissingValueRegistry()
    try:
        metrics = MetricsLoader(ticker, registry=registry).build_stock_metrics()
        missing_count = len(registry)
        if missing_count:
            logger.info(
                "Stock metrics retrieved for %s. Missing fields recorded: %d",
                ticker, missing_count,
            )
        else:
            logger.info("Stock metrics retrieved successfully for %s.", ticker)
        return metrics, registry
    except Exception as e:
        logger.error("Failed to retrieve data for %s: %s", ticker, e)
        sys.exit(1)


def run_suitability_check(
    manager: ValuationManager,
    method_name: str,
    registry: MissingValueRegistry,
) -> ValuationCheckResult:
    logger.info("Running suitability check for %s...", method_name)
    try:
        result = manager.validate_metrics(registry=registry)
    except Exception as e:
        logger.error("Error during %s suitability evaluation: %s", method_name, e)
        result = ValuationCheckResult(
            ticker=manager.stock_metrics.profile.ticker,
            is_suitable=False,
            total_severity_score=100,
            interpretation=f"Suitability evaluation failed: {e}",
            factors=[],
        )
    for factor in result.factors:
        logger.info(" [%s] %s", factor.severity.value, factor.message)
    logger.info("Total Severity Score: %s", result.total_severity_score)
    logger.info("Interpretation: %s", result.interpretation)
    return result


def run_valuation(
    manager: ValuationManager,
    registry: MissingValueRegistry,
    print_cli: bool,
) -> ModelRunOutcome:
    """
    Run suitability check + valuation for one manager.

    Returns a structured outcome so run_for_ticker() can collect suitability,
    valuation, skip, and error state for one coherent JSON document.
    """
    manager_cls = manager.__class__
    model_name = manager_cls.__name__.replace("Manager", "")
    method_name = model_name.upper()
    check_result = run_suitability_check(manager, method_name, registry)

    if check_result.total_severity_score >= _VALUATION_SKIP_THRESHOLD:
        logger.warning(
            "--- %s valuation skipped due to high severity score: %d (%s) ---",
            method_name, check_result.total_severity_score, check_result.interpretation,
        )
        return ModelRunOutcome(
            model_name=model_name,
            suitability_result=check_result,
            valuation_report=None,
            was_skipped=True,
        )

    logger.info("Running %s valuation...", method_name)
    try:
        valuation_report = manager.execute_valuation_scenarios()
        if print_cli:
            presenter = CLI_PRESENTERS.get(manager_cls)
            if not presenter:
                logger.warning("No CLI presenter registered for %s.", manager_cls.__name__)
            else:
                print(f"--- {method_name} Result CLI ---")
                presenter(manager.stock_metrics, valuation_report)
        if not print_cli:
            logger.info("%s valuation completed successfully.", method_name)
        return ModelRunOutcome(
            model_name=model_name,
            suitability_result=check_result,
            valuation_report=valuation_report,
            was_skipped=False,
        )
    except Exception as e:
        logger.error("Failed to run %s analysis: %s", method_name, e)
        return ModelRunOutcome(
            model_name=model_name,
            suitability_result=check_result,
            valuation_report=None,
            was_skipped=True,
            error=str(e),
        )


def _extract_summary_rows(
    manager_cls: Type[ValuationManager],
    valuation_report: object,
    current_price: float,
) -> List[ModelScenarioRow]:
    """
    DESIGN-D: extract (model, scenario, intrinsic_value, status) rows
    from a valuation report for inclusion in ValuationSummaryReport.

    Handles scenario-based intrinsic reports. Reverse DCF and other
    non-scenario diagnostic reports are skipped by design.
    """
    model_name = manager_cls.__name__.replace("Manager", "")
    rows: List[ModelScenarioRow] = []

    scenarios = getattr(valuation_report, "scenarios", None)
    if not scenarios:
        return rows

    for scenario_name, result in scenarios.items():
        iv: Optional[float] = (
            getattr(result, "intrinsic_value_per_share", None)
            or getattr(result, "present_value", None)
            or getattr(result, "intrinsic_value", None)
        )
        if iv is None:
            continue

        status = getattr(result, "valuation_status", "unknown")
        implied_upside = (iv / current_price - 1.0) if current_price > 0 else 0.0

        rows.append(ModelScenarioRow(
            model_name=model_name,
            scenario=scenario_name,
            intrinsic_value=iv,
            valuation_status=status,
            implied_upside=implied_upside,
        ))

    return rows


def _missing_data_payload(registry: MissingValueRegistry) -> Dict[str, object]:
    return {
        "count": len(registry),
        "summary": registry.summary(),
        "entries": list(registry),
    }


def _skipped_models_payload(
    outcomes: List[ModelRunOutcome],
) -> Dict[str, Dict[str, Any]]:
    skipped: Dict[str, Dict[str, Any]] = {}
    for outcome in outcomes:
        if not outcome.was_skipped:
            continue
        skipped[outcome.model_name] = {
            "reason": outcome.error or outcome.suitability_result.interpretation,
            "total_severity_score": outcome.suitability_result.total_severity_score,
            "is_suitable": outcome.suitability_result.is_suitable,
            "error": outcome.error,
        }
    return skipped


def _build_json_payload(
    ticker: str,
    stock_metrics: StockMetrics,
    registry: MissingValueRegistry,
    outcomes: List[ModelRunOutcome],
    summary: ValuationSummaryReport,
) -> Dict[str, object]:
    return {
        "ticker": ticker,
        "stock_metrics": stock_metrics,
        "missing_data": _missing_data_payload(registry),
        "suitability": {
            outcome.model_name: outcome.suitability_result for outcome in outcomes
        },
        "valuations": {
            outcome.model_name: outcome.valuation_report
            for outcome in outcomes
            if not outcome.was_skipped and outcome.valuation_report is not None
        },
        "skipped_models": _skipped_models_payload(outcomes),
        "summary": summary,
    }


def run_for_ticker(
    config: RunConfig,
    managers: List[Type[ValuationManager]],
) -> None:
    logger.info("Starting valuation for %s", config.ticker)
    stock_metrics, registry = fetch_stock_metrics(config.ticker)

    current_price = stock_metrics.market_data.current_price

    # DESIGN-D: collect results for consolidated summary
    all_summary_rows:  List[ModelScenarioRow] = []
    models_run:        List[str] = []
    models_skipped:    List[str] = []
    outcomes:          List[ModelRunOutcome] = []

    for ManagerClass in managers:
        manager_instance = ManagerClass(stock_metrics=stock_metrics)

        outcome = run_valuation(
            manager_instance,
            registry,
            print_cli=config.print_cli,
        )
        outcomes.append(outcome)

        if outcome.was_skipped or outcome.valuation_report is None:
            models_skipped.append(outcome.model_name)
        else:
            models_run.append(outcome.model_name)
            rows = _extract_summary_rows(
                ManagerClass,
                outcome.valuation_report,
                current_price,
            )
            all_summary_rows.extend(rows)

    # DESIGN-D: build and emit ValuationSummaryReport
    summary = ValuationSummaryReport.build(
        ticker=config.ticker,
        current_price=current_price,
        rows=all_summary_rows,
        models_run=models_run,
        models_skipped=models_skipped,
    )

    if config.print_cli:
        cli_print_summary(summary, current_price)

    if config.print_json:
        payload = _build_json_payload(
            ticker=config.ticker,
            stock_metrics=stock_metrics,
            registry=registry,
            outcomes=outcomes,
            summary=summary,
        )
        if config.print_cli:
            print("--- JSON Result ---")
        print(to_json(payload, compact=True))


def parse_arguments() -> RunConfig:
    parser = argparse.ArgumentParser(description="Run multiple stock valuations.")
    parser.add_argument("ticker", nargs="?", help="Ticker symbol (e.g., AAPL)")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--cli",  action="store_true")
    output_group.add_argument("--json", action="store_true")
    output_group.add_argument("--all",  action="store_true")
    parser.add_argument(
        "--reverse-dcf",
        action="store_true",
        help="Include Reverse DCF implied-growth diagnostics in the run.",
    )
    args = parser.parse_args()

    ticker = args.ticker or input("Enter ticker symbol (e.g., AAPL): ").strip()
    if not ticker:
        logger.error("No ticker symbol provided. Exiting.")
        sys.exit(1)

    return RunConfig(
        ticker=ticker.upper(),
        print_cli=args.cli  or args.all,
        print_json=args.json or args.all,
        include_reverse_dcf=args.reverse_dcf,
    )


def main() -> None:
    config = parse_arguments()
    managers = list(VALUATION_MANAGERS)
    if config.include_reverse_dcf:
        managers.append(ReverseDCFManager)
    run_for_ticker(config, managers=managers)


if __name__ == "__main__":
    main()
