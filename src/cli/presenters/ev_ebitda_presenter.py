from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.ev_ebitda import EVEBITDAValuationReport

from .utils import colors, fmt_num


def _status_colored(status: str) -> str:
    if "undervalued" in status:
        return f"{colors.GREEN.value}{status}{colors.RESET.value}"
    if "overvalued" in status:
        return f"{colors.RED.value}{status}{colors.RESET.value}"
    return status


def cli_print_valuation(metrics: StockMetrics, report: EVEBITDAValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: EVEBITDAValuationReport for {ticker} contains no scenarios.")
        return

    print(f"====================== EV/EBITDA Valuation for {ticker} ======================\n")
    print(tabulate(
        [
            ["Current Stock Price", fmt_num(metrics.market_data.current_price)],
            ["EBITDA (TTM)", fmt_num(report.ebitda_ttm)],
            ["Current EV/EBITDA", fmt_num(getattr(metrics.ratios, "ev_ebitda", None))],
            ["Enterprise Value", fmt_num(metrics.valuation.enterprise_value)],
        ],
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
    ))
    print()

    rows = []
    for scenario_name, r in report.scenarios.items():
        rows.append([
            scenario_name,
            fmt_num(r.ebitda_multiple_used),
            fmt_num(r.intrinsic_ev),
            fmt_num(r.equity_value),
            fmt_num(r.intrinsic_value_per_share),
            _status_colored(r.valuation_status),
        ])

    print(tabulate(
        rows,
        headers=["Scenario", "Multiple", "Intrinsic EV", "Equity Value", "IV/Share", "Status"],
        tablefmt="fancy_grid",
    ))
    print()
