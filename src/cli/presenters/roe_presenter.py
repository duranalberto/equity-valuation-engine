from tabulate import tabulate
from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import ROEValuationResult
from domain.valuation.base import ValuationReport
from .utils import fmt_num, fmt_pct, colors
from typing import List



def build_summary_metrics_table(metrics: StockMetrics) -> List[List[str]]:
    """Builds the table of key input metrics common to all scenarios."""
    current_price = metrics.market_data.current_price

    bvs = getattr(getattr(metrics, 'ratios', None), 'book_value_per_share', None)
    roe = getattr(getattr(metrics, 'ratios', None), 'return_on_equity', None)
    dividend_yield = getattr(getattr(metrics, 'ratios', None), 'dividend_yield', None)
    
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["Book Value per Share (BVS)", fmt_num(bvs) if bvs is not None else "-"],
        ["Return on Equity (ROE) (TTM)", fmt_pct(roe) if roe is not None else "-"],
        ["Current Dividend Yield", fmt_pct(dividend_yield) if dividend_yield is not None else "-"],
    ]


def build_scenario_summary_table(report: ValuationReport) -> List[List[str]]:
    """
    Builds the final valuation summary table comparing intrinsic value across all ROE scenarios.
    """
    summary_table = []

    for scenario_name, r_untyped in report.scenarios.items():
        r: ROEValuationResult = r_untyped 
        status = r.valuation_status
        
        if "undervalued" in status:
            status_colored = f"{colors.GREEN.value}{status}{colors.RESET.value}"
        elif "overvalued" in status:
            status_colored = f"{colors.RED.value}{status}{colors.RESET.value}"
        else:
            status_colored = status

        summary_table.append([
            scenario_name,
            fmt_num(r.intrisic_value),
            fmt_num(r.npv_dividends),
            fmt_num(r.npv_required_value),
            status_colored,
        ])

    return summary_table



def build_equity_progression_table(report: ValuationReport) -> List[List[str]]:
    """Builds a table showing the projected Shareholders' Equity per Share."""
    equity_table = []
    for scenario_name, r_untyped in report.scenarios.items():
        r: ROEValuationResult = r_untyped
        
        equity_table.append(
            [scenario_name] + [fmt_num(v) for v in r.shareholders_equity_progression]
        )
    return equity_table



def build_dividend_progression_table(report: ValuationReport) -> List[List[str]]:
    """Builds a table showing the projected Dividends per Share for all scenarios."""
    dividend_table = []
    for scenario_name, r_untyped in report.scenarios.items():
        r: ROEValuationResult = r_untyped
        
        dividend_table.append(
            [scenario_name] + [fmt_num(v) for v in r.dividend_progression]
        )
    return dividend_table



def build_npv_dividend_progression_table(report: ValuationReport) -> List[List[str]]:
    """Builds a table showing the NPV of projected Dividends per Share for all scenarios."""
    npv_table = []
    for scenario_name, r_untyped in report.scenarios.items():
        r: ROEValuationResult = r_untyped
        
        npv_table.append(
            [scenario_name] + [fmt_num(v) for v in r.npv_dividend_progression]
        )
    return npv_table



def cli_print_valuation(
    metrics: StockMetrics,
    report: ValuationReport 
):
    """
    Prints the Return on Equity (ROE) valuation report, displaying results 
    and detailed progression across all scenarios, separated into three tables.
    """
    ticker = metrics.profile.ticker
    
    if not report.scenarios:
        print(f"ERROR: ROEValuationReport for {ticker} contains no scenarios.")
        return

    first_result: ROEValuationResult = next(iter(report.scenarios.values()))
    
    if not first_result.dividend_progression:
        print(f"ERROR: ROEValuationResult for {ticker} contains no dividend projections.")
        return
        
    proj_len = len(first_result.dividend_progression)
    year_headers = [f"Year {i+1}" for i in range(proj_len)]
    
    print(f"======================== ROE Valuation Comparison for {ticker} ========================\n")


    summary_info = build_summary_metrics_table(metrics) 
    print(tabulate(summary_info, headers=["Metric", "Value"], tablefmt="fancy_grid", colalign=("left", "left")))
    print()


    print("\n-- Scenario Valuation Summary --")
    summary_headers = [
        "Scenario", "Intrinsic Value", "Total NPV Dividends", 
        "NPV Terminal Value", "Status" 
    ]
    summary_table = build_scenario_summary_table(report)
    colaligns = ("left", "decimal", "decimal", "decimal", "left")
    print(tabulate(summary_table, headers=summary_headers, tablefmt="fancy_grid", colalign=colaligns))
    print()
    

    print("\n-- 1. Shareholders' Equity Progression (Per Share) --")
    equity_table = build_equity_progression_table(report)
    equity_headers = ["Scenario"] + year_headers
    print(tabulate(equity_table, headers=equity_headers, tablefmt="fancy_grid"))
    print()
    

    print("\n-- 2. Dividend Progression (Per Share) --")
    dividend_table = build_dividend_progression_table(report)
    dividend_headers = ["Scenario"] + year_headers
    print(tabulate(dividend_table, headers=dividend_headers, tablefmt="fancy_grid"))
    print()


    print("\n-- 3. NPV Dividend Progression (Per Share) --")
    npv_table = build_npv_dividend_progression_table(report)
    npv_headers = ["Scenario"] + year_headers
    print(tabulate(npv_table, headers=npv_headers, tablefmt="fancy_grid"))
    print()