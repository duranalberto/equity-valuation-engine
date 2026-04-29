from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.ps import PSValuationReport

from .utils import colors, fmt_num


def _status_colored(status: str) -> str:
    if "undervalued" in status:
        return f"{colors.GREEN.value}{status}{colors.RESET.value}"
    if "overvalued" in status:
        return f"{colors.RED.value}{status}{colors.RESET.value}"
    return status


def cli_print_valuation(metrics: StockMetrics, report: PSValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: PSValuationReport for {ticker} contains no scenarios.")
        return

    first = next(iter(report.scenarios.values()))

    print(f"======================== P/S Valuation for {ticker} ========================\n")
    print(tabulate(
        [
            ["Current Stock Price", fmt_num(metrics.market_data.current_price)],
            ["Revenue (TTM)", fmt_num(report.revenue_ttm)],
            ["Current Implied P/S", fmt_num(first.implied_revenue_multiple)],
            ["Market Cap", fmt_num(metrics.market_data.market_cap)],
        ],
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
    ))
    print()

    rows = []
    for scenario_name, r in report.scenarios.items():
        rows.append([
            scenario_name,
            fmt_num(r.ps_multiple_used),
            fmt_num(r.intrinsic_market_cap),
            fmt_num(r.intrinsic_value_per_share),
            _status_colored(r.valuation_status),
        ])

    print(tabulate(
        rows,
        headers=["Scenario", "P/S Multiple", "Intrinsic Market Cap", "IV/Share", "Status"],
        tablefmt="fancy_grid",
    ))
    print()
