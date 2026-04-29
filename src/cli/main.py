import argparse
import logging
import sys
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple, Type

from application import DCFManager, MetricsLoader, PEManager, ROEManager
from cli.json_formatter import to_json
from domain import StockMetrics
from domain.core.missing_registry import MissingValueRegistry
from domain.valuation.models.summary import ModelScenarioRow, ValuationSummaryReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .presenters.dcf_presenter import cli_print_valuation as dcf_print
from .presenters.pe_presenter import cli_print_valuation as pe_print
from .presenters.roe_presenter import cli_print_valuation as roe_print
from .presenters.summary_presenter import cli_print_summary


class RunConfig(NamedTuple):
    ticker:     str
    print_cli:  bool
    print_json: bool


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALUATION_MANAGERS: List[Type[ValuationManager]] = [DCFManager, PEManager, ROEManager]

CLI_PRESENTERS: Dict[Type[ValuationManager], Callable] = {
    DCFManager: dcf_print,
    PEManager:  pe_print,
    ROEManager: roe_print,
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


def display_stock_metrics(
    stock_metrics: StockMetrics,
    print_json: bool,
) -> None:
    if print_json:
        print("--- Stock Metrics JSON ---")
        print(to_json(stock_metrics, compact=True))


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
    print_json: bool,
) -> Tuple[Optional[object], bool]:
    """
    Run suitability check + valuation for one manager.

    Returns (valuation_report, was_skipped).
    DESIGN-D: returns the report so run_for_ticker() can collect it for
    the consolidated ValuationSummaryReport.
    """
    manager_cls = manager.__class__
    method_name = manager_cls.__name__.replace("Manager", "").upper()
    check_result = run_suitability_check(manager, method_name, registry)

    if check_result.total_severity_score >= _VALUATION_SKIP_THRESHOLD:
        logger.warning(
            "--- %s valuation skipped due to high severity score: %d (%s) ---",
            method_name, check_result.total_severity_score, check_result.interpretation,
        )
        return None, True  # (no report, was_skipped=True)

    logger.info("Running %s valuation...", method_name)
    try:
        valuation_report = manager.execute_valuation_scenarios()
        if print_json:
            print(f"--- {method_name} Result JSON ---")
            print(to_json(valuation_report, compact=True))
        if print_cli:
            presenter = CLI_PRESENTERS.get(manager_cls)
            if not presenter:
                logger.warning("No CLI presenter registered for %s.", manager_cls.__name__)
            else:
                print(f"--- {method_name} Result CLI ---")
                presenter(manager.stock_metrics, valuation_report)
        if not print_cli and not print_json:
            logger.info(
                "%s valuation completed successfully (no output flags).", method_name
            )
        return valuation_report, False  # (report, was_skipped=False)
    except Exception as e:
        logger.error("Failed to run %s analysis: %s", method_name, e)
        return None, True


def _extract_summary_rows(
    manager_cls: Type[ValuationManager],
    valuation_report: object,
    current_price: float,
) -> List[ModelScenarioRow]:
    """
    DESIGN-D: extract (model, scenario, intrinsic_value, status) rows
    from a valuation report for inclusion in ValuationSummaryReport.

    Handles DCF, P/E, and ROE report shapes.  Unknown shapes are silently
    skipped so new models added in Phase 4 don't require changes here.
    """
    model_name = manager_cls.__name__.replace("Manager", "")
    rows: List[ModelScenarioRow] = []

    scenarios = getattr(valuation_report, "scenarios", None)
    if not scenarios:
        return rows

    for scenario_name, result in scenarios.items():
        # Intrinsic value field differs by model type
        iv: Optional[float] = (
            getattr(result, "intrinsic_value_per_share", None)  # DCF
            or getattr(result, "present_value", None)           # P/E
            or getattr(result, "intrinsic_value", None)         # ROE
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


def run_for_ticker(
    config: RunConfig,
    managers: List[Type[ValuationManager]],
) -> None:
    logger.info("Starting valuation for %s", config.ticker)
    stock_metrics, registry = fetch_stock_metrics(config.ticker)
    display_stock_metrics(stock_metrics, config.print_json)

    current_price = stock_metrics.market_data.current_price

    # DESIGN-D: collect results for consolidated summary
    all_summary_rows:  List[ModelScenarioRow] = []
    models_run:        List[str] = []
    models_skipped:    List[str] = []

    for ManagerClass in managers:
        manager_instance = ManagerClass(stock_metrics=stock_metrics)
        model_name = ManagerClass.__name__.replace("Manager", "")

        report, was_skipped = run_valuation(
            manager_instance,
            registry,
            print_cli=config.print_cli,
            print_json=config.print_json,
        )

        if was_skipped or report is None:
            models_skipped.append(model_name)
        else:
            models_run.append(model_name)
            rows = _extract_summary_rows(ManagerClass, report, current_price)
            all_summary_rows.extend(rows)

    # DESIGN-D: build and emit ValuationSummaryReport
    summary = ValuationSummaryReport.build(
        ticker=config.ticker,
        current_price=current_price,
        rows=all_summary_rows,
        models_run=models_run,
        models_skipped=models_skipped,
    )

    if config.print_json:
        # Emit summary as top-level "summary" key in JSON output
        import dataclasses
        import json

        def _to_dict(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_to_dict(i) for i in obj]
            if isinstance(obj, tuple):
                return [_to_dict(i) for i in obj]
            if isinstance(obj, float):
                return round(obj, 4) if obj == obj else None  # handle NaN
            return obj

        print("--- Summary JSON ---")
        print(json.dumps({"summary": _to_dict(summary)}, separators=(",", ":")))

    if config.print_cli:
        cli_print_summary(summary, current_price)


def parse_arguments() -> RunConfig:
    parser = argparse.ArgumentParser(description="Run multiple stock valuations.")
    parser.add_argument("ticker", nargs="?", help="Ticker symbol (e.g., AAPL)")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--cli",  action="store_true")
    output_group.add_argument("--json", action="store_true")
    output_group.add_argument("--all",  action="store_true")
    args = parser.parse_args()

    ticker = args.ticker or input("Enter ticker symbol (e.g., AAPL): ").strip()
    if not ticker:
        logger.error("No ticker symbol provided. Exiting.")
        sys.exit(1)

    return RunConfig(
        ticker=ticker.upper(),
        print_cli=args.cli  or args.all,
        print_json=args.json or args.all,
    )


def main() -> None:
    config = parse_arguments()
    run_for_ticker(config, managers=VALUATION_MANAGERS)


if __name__ == "__main__":
    main()