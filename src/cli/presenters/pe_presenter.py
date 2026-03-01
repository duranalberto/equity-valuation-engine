from tabulate import tabulate
from domain.metrics.stock import StockMetrics
from domain.valuation.models.pe import PEValuationResult
from domain.valuation.base import ValuationReport
from .utils import fmt_num, fmt_pct, colors
from typing import List, Any 


def build_summary_metrics_table(metrics: StockMetrics) -> List[List[str]]:
    """Builds the table of key input metrics common to all scenarios."""
    current_price = metrics.market_data.current_price
    pe_ttm = metrics.market_data.pe_ttm
    
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["Current P/E Ratio (TTM)", fmt_num(pe_ttm)],
    ]

def build_scenario_summary_table(report: ValuationReport) -> List[List[str]]:
    """
    Builds the summary table comparing intrinsic value across all PE scenarios.
    """
    summary_table = []
    for scenario_name, r_untyped in report.scenarios.items():
        r: PEValuationResult = r_untyped 
        
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
            scenario_name,
            fmt_num(r.present_value),
            fmt_num(r.value_in_x_years),
            fmt_pct(total_growth),
            status_colored,
        ])

    return summary_table


def build_eps_progression_table(report: ValuationReport) -> List[List[str]]:
    """Builds a table showing the projected EPS growth for all scenarios."""
    
    eps_table = []
    
    for scenario_name, r_untyped in report.scenarios.items():
        r: PEValuationResult = r_untyped 
        proj = r.eps_progression 
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None

        eps_table.append(
            [scenario_name] + [fmt_num(v) for v in proj] + [fmt_pct(total_growth)]
        )
    return eps_table


def cli_print_valuation(
    metrics: StockMetrics,
    report: ValuationReport 
):
    """
    Prints the Price-to-Earnings (PE) valuation report, displaying results 
    and projections across all scenarios in the report.
    """
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


    summary_info = build_summary_metrics_table(metrics) 
    print(tabulate(summary_info, headers=["Metric", "Value"], tablefmt="fancy_grid", colalign=("left", "decimal")))
    print()

    print("\n-- Scenario Valuation Summary --")
    summary_headers = [
        "Scenario", "Intrinsic Value", "Future Value", 
        "Total EPS Growth", "Status" 
    ]
    summary_table = build_scenario_summary_table(report)
    colaligns = ("left", "decimal", "decimal", "decimal", "left")
    print(tabulate(summary_table, headers=summary_headers, tablefmt="fancy_grid", colalign=colaligns))
    print()
    
    print("\n-- Projected Earnings Per Share (EPS) by Scenario --")

    eps_headers = ["Scenario"] + [f"Year {i+1}" for i in range(proj_len)] + ["Total Growth"]
    eps_table = build_eps_progression_table(report)
    
    print(tabulate(eps_table, headers=eps_headers, tablefmt="fancy_grid"))
    print()