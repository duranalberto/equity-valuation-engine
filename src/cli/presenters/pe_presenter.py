from tabulate import tabulate
from domain.metrics.stock import StockMetrics
from domain.valuation.models.pe import PEValuationResult, PEValuationReport
from .utils import fmt_num, fmt_pct, colors
from typing import List


def build_summary_metrics_table(metrics: StockMetrics):
    return [
        ["Current Stock Price", fmt_num(metrics.market_data.current_price)],
        ["Current P/E Ratio (TTM)", fmt_num(metrics.market_data.pe_ttm)],
    ]


def build_scenario_summary_table(report: PEValuationReport):
    summary_table = []
    for scenario_name, r in report.scenarios.items():
        status = r.valuation_status
        if "undervalued" in status:
            status_colored = f"{colors.GREEN.value}{status}{colors.RESET.value}"
        elif "overvalued" in status:
            status_colored = f"{colors.RED.value}{status}{colors.RESET.value}"
        else:
            status_colored = status
        proj = r.eps_progression
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None
        summary_table.append([
            scenario_name, fmt_num(r.present_value), fmt_num(r.value_in_x_years),
            fmt_pct(total_growth), status_colored,
        ])
    return summary_table


def build_eps_progression_table(report: PEValuationReport):
    eps_table = []
    for scenario_name, r in report.scenarios.items():
        proj = r.eps_progression
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None
        eps_table.append([scenario_name] + [fmt_num(v) for v in proj] + [fmt_pct(total_growth)])
    return eps_table


def cli_print_valuation(metrics: StockMetrics, report: PEValuationReport) -> None:
    ticker = metrics.profile.ticker
    if not report.scenarios:
        print(f"ERROR: PEValuationReport for {ticker} contains no scenarios.")
        return

    first_result: PEValuationResult = next(iter(report.scenarios.values()))
    if not first_result.eps_progression:
        print(f"ERROR: PEValuationResult for {ticker} contains no EPS projections.")
        return

    proj_len = len(first_result.eps_progression)

    print(f"======================== P/E Valuation Comparison for {ticker} ========================\n")
    print(tabulate(build_summary_metrics_table(metrics), headers=["Metric", "Value"], tablefmt="fancy_grid", colalign=("left", "decimal")))
    print()
    print("\n-- Scenario Valuation Summary --")
    print(tabulate(build_scenario_summary_table(report), headers=["Scenario", "Intrinsic Value", "Future Value", "Total EPS Growth", "Status"], tablefmt="fancy_grid", colalign=("left", "decimal", "decimal", "decimal", "left")))
    print()
    print("\n-- Projected Earnings Per Share (EPS) by Scenario --")
    eps_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(proj_len)] + ["Total Growth"]
    print(tabulate(build_eps_progression_table(report), headers=eps_headers, tablefmt="fancy_grid"))
    print()
