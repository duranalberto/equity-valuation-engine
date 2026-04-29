from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.ddm import DDMValuationReport

from .utils import colors, fmt_num, fmt_pct


def _status_colored(status: str) -> str:
    if "undervalued" in status:
        return f"{colors.GREEN.value}{status}{colors.RESET.value}"
    if "overvalued" in status:
        return f"{colors.RED.value}{status}{colors.RESET.value}"
    return status


def cli_print_valuation(metrics: StockMetrics, report: DDMValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: DDMValuationReport for {ticker} contains no scenarios.")
        return

    print(f"======================== DDM Valuation for {ticker} ========================\n")
    print(tabulate(
        [
            ["Current Stock Price", fmt_num(metrics.market_data.current_price)],
            ["Dividend Per Share (TTM)", fmt_num(report.dps_ttm)],
            ["Dividend Growth Rate", fmt_pct(report.dividend_growth_rate)],
            ["Terminal Growth Rate", fmt_pct(report.params.terminal_growth_rate)],
        ],
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
    ))
    print()

    rows = []
    for scenario_name, r in report.scenarios.items():
        rows.append([
            scenario_name,
            fmt_pct(r.growth_rates[0] if r.growth_rates else None),
            fmt_pct(r.required_return),
            fmt_num(r.intrinsic_value_per_share),
            fmt_num(r.pv_dividends),
            fmt_num(r.pv_terminal_value),
            fmt_pct(r.implied_required_return),
            fmt_pct(r.dividend_yield_implied),
            _status_colored(r.valuation_status),
        ])

    print(tabulate(
        rows,
        headers=[
            "Scenario",
            "Growth",
            "Required Return",
            "IV/Share",
            "PV Dividends",
            "PV Terminal",
            "Implied Return",
            "Implied Div Yield",
            "Status",
        ],
        tablefmt="fancy_grid",
    ))
    print()
