from tabulate import tabulate
from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import ROEValuationResult, ROEValuationReport
from .utils import fmt_num, fmt_pct, colors
from typing import List


def build_summary_metrics_table(metrics: StockMetrics):
    current_price = metrics.market_data.current_price
    bvs = getattr(getattr(metrics, "ratios", None), "book_value_per_share", None)
    roe = getattr(getattr(metrics, "ratios", None), "return_on_equity", None)
    dividend_yield = getattr(getattr(metrics, "ratios", None), "dividend_yield", None)
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["Book Value per Share (BVS)", fmt_num(bvs) if bvs is not None else "-"],
        ["Return on Equity (ROE) (TTM)", fmt_pct(roe) if roe is not None else "-"],
        ["Current Dividend Yield", fmt_pct(dividend_yield) if dividend_yield is not None else "-"],
    ]


def build_scenario_summary_table(report: ROEValuationReport):
    summary_table = []
    for scenario_name, r in report.scenarios.items():
        status = r.valuation_status
        if "undervalued" in status:
            status_colored = f"{colors.GREEN.value}{status}{colors.RESET.value}"
        elif "overvalued" in status:
            status_colored = f"{colors.RED.value}{status}{colors.RESET.value}"
        else:
            status_colored = status
        summary_table.append([
            scenario_name, fmt_num(r.intrinsic_value), fmt_num(r.npv_dividends),
            fmt_num(r.npv_required_value), status_colored,
        ])
    return summary_table


def cli_print_valuation(metrics: StockMetrics, report: ROEValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: ROEValuationReport for {ticker} contains no scenarios.")
        return

    first_result: ROEValuationResult = next(iter(report.scenarios.values()))
    if not first_result.dividend_progression:
        print(f"ERROR: ROEValuationResult for {ticker} contains no dividend projections.")
        return

    proj_len = len(first_result.dividend_progression)
    year_headers = [f"Year {i + 1}" for i in range(proj_len)]

    print(f"======================== ROE Valuation Comparison for {ticker} ========================\n")
    print(tabulate(build_summary_metrics_table(metrics), headers=["Metric", "Value"], tablefmt="fancy_grid", colalign=("left", "left")))
    print()
    print("\n-- Scenario Valuation Summary --")
    print(tabulate(build_scenario_summary_table(report), headers=["Scenario", "Intrinsic Value", "Total NPV Dividends", "NPV Terminal Value", "Status"], tablefmt="fancy_grid", colalign=("left", "decimal", "decimal", "decimal", "left")))
    print()
    print("\n-- 1. Shareholders' Equity Progression (Per Share) --")
    print(tabulate([[sn] + [fmt_num(v) for v in r.shareholders_equity_progression] for sn, r in report.scenarios.items()], headers=["Scenario"] + year_headers, tablefmt="fancy_grid"))
    print()
    print("\n-- 2. Dividend Progression (Per Share) --")
    print(tabulate([[sn] + [fmt_num(v) for v in r.dividend_progression] for sn, r in report.scenarios.items()], headers=["Scenario"] + year_headers, tablefmt="fancy_grid"))
    print()
    print("\n-- 3. NPV Dividend Progression (Per Share) --")
    print(tabulate([[sn] + [fmt_num(v) for v in r.npv_dividend_progression] for sn, r in report.scenarios.items()], headers=["Scenario"] + year_headers, tablefmt="fancy_grid"))
    print()
