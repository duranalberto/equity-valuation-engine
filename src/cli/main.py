import sys
import logging
import argparse
from typing import List, Type, NamedTuple, Callable, Dict

from domain import StockMetrics
from domain.valuation.valuation_manager import ValuationManager
from domain.valuation.policies import ValuationCheckResult

from application import DCFManager, PEManager, ROEManager, MetricsLoader
from cli.json_formatter import to_json

from .presenters.dcf_presenter import cli_print_valuation as dcf_print
from .presenters.pe_presenter import cli_print_valuation as pe_print
from .presenters.roe_presenter import cli_print_valuation as roe_print


class RunConfig(NamedTuple):
    ticker: str
    print_cli: bool
    print_json: bool



logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALUATION_MANAGERS: List[Type[ValuationManager]] = [
    DCFManager,
    PEManager,
    ROEManager,
]

CLI_PRESENTERS: Dict[Type[ValuationManager], Callable] = {
    DCFManager: dcf_print,
    PEManager: pe_print,
    ROEManager: roe_print,
}


def fetch_stock_metrics(ticker: str) -> StockMetrics:
    """Fetch stock metrics for a given ticker."""
    try:
        metrics = MetricsLoader(ticker).build_stock_metrics()
        logger.info("Stock metrics retrieved successfully for %s.", ticker)
        return metrics
    except Exception as e:
        logger.error("Failed to retrieve data for %s: %s", ticker, e)
        sys.exit(1)


def display_stock_metrics(stock_metrics: StockMetrics, print_json: bool) -> None:
    """Display stock metrics as JSON if enabled."""
    if print_json:
        print("--- Stock Metrics JSON ---")
        print(to_json(stock_metrics, compact=True))


def run_suitability_check(
    manager: ValuationManager,
    method_name: str
) -> ValuationCheckResult:
    """Run the suitability check for a valuation manager."""
    logger.info("Running suitability check for %s...", method_name)

    try:
        result = manager.validate_metrics()
    except Exception as e:
        logger.error(
            "Error during %s suitability evaluation: %s",
            method_name,
            e,
        )
        result = ValuationCheckResult(
            ticker=manager.stock_metrics.profile.ticker,
            is_suitable=False,
            total_severity_score=100,
            interpretation=f"Suitability evaluation failed: {e}",
            factors=[],
        )

    logger.info("Suitability Check Results for %s:", method_name)
    for factor in result.factors:
        logger.info(" [%s] %s", factor.severity.value, factor.message)

    logger.info("Total Severity Score: %s", result.total_severity_score)
    logger.info("Interpretation: %s", result.interpretation)

    return result


def run_valuation(
    manager: ValuationManager,
    print_cli: bool,
    print_json: bool,
) -> None:
    """Run valuation with suitability check and selected outputs."""
    manager_cls = manager.__class__
    method_name = manager_cls.__name__.replace("Manager", "").upper()
    check_result = run_suitability_check(manager, method_name)

    if check_result.total_severity_score > 10:
        logger.warning(
            "--- %s valuation skipped due to high severity score: %d (%s) ---",
            method_name,
            check_result.total_severity_score,
            check_result.interpretation,
        )
        return

    logger.info("Running %s valuation...", method_name)

    try:
        valuation_report = manager.execute_valuation_scenarios()

        if print_json:
            print(f"--- {method_name} Result JSON ---")
            print(to_json(valuation_report, compact=True))

        if print_cli:
            presenter = CLI_PRESENTERS.get(manager_cls)
            if not presenter:
                logger.warning(
                    "No CLI presenter registered for %s.",
                    manager_cls.__name__,
                )
            else:
                print(f"--- {method_name} Result CLI ---")
                presenter(valuation_report)

        if not print_cli and not print_json:
            logger.info(
                "%s valuation completed successfully (no output flags).",
                method_name,
            )

    except Exception as e:
        logger.error("Failed to run %s analysis: %s", method_name, e)



def run_for_ticker(
    config: RunConfig,
    managers: List[Type[ValuationManager]],
) -> None:
    """Fetch metrics and run all valuation managers."""
    logger.info("Starting valuation for %s", config.ticker)

    stock_metrics = fetch_stock_metrics(config.ticker)
    display_stock_metrics(stock_metrics, config.print_json)

    for ManagerClass in managers:
        manager_instance = ManagerClass(stock_metrics=stock_metrics)
        run_valuation(
            manager_instance,
            print_cli=config.print_cli,
            print_json=config.print_json,
        )


def parse_arguments() -> RunConfig:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run multiple stock valuations."
    )
    parser.add_argument("ticker", nargs="?", help="Ticker symbol (e.g., AAPL)")

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--cli", action="store_true")
    output_group.add_argument("--json", action="store_true")
    output_group.add_argument("--all", action="store_true")

    args = parser.parse_args()

    ticker = args.ticker or input("Enter ticker symbol (e.g., AAPL): ").strip()
    if not ticker:
        logger.error("No ticker symbol provided. Exiting.")
        sys.exit(1)

    return RunConfig(
        ticker=ticker.upper(),
        print_cli=args.cli or args.all,
        print_json=args.json or args.all,
    )


def main() -> None:
    config = parse_arguments()
    run_for_ticker(config, managers=VALUATION_MANAGERS)


if __name__ == "__main__":
    main()
