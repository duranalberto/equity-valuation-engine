from tabulate import tabulate
from domain.valuation.models.dcf import DCFValuationReport
from domain.metrics.stock import StockMetrics
from .utils import fmt_num, fmt_pct, colors
from typing import List


def build_summary_metrics_table(current_price: float, pe_ratio: float, report: DCFValuationReport) -> List[List[str]]:
    cost_of_equity = report.wacc.cost_of_equity
    
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["P/E Ratio", fmt_num(pe_ratio)],
        ["Cost of Equity", fmt_pct(cost_of_equity)],
        ["WACC", fmt_pct(report.wacc.wacc)],
    ]


def build_scenario_summary_table(report: DCFValuationReport) -> List[List[str]]:
    """
    Builds the summary table comparing intrinsic value across scenarios.
    The scenario name is taken from the dictionary key.
    """
    summary_table = []

    for scenario_name, r in report.scenarios.items():
        intrinsic = r.intrinsic_value_per_share
        status = r.valuation_status

        if "undervalued" in status:
            status_colored = f"{colors.GREEN.value}{status}{colors.RESET.value}"
        elif "overvalued" in status:
            status_colored = f"{colors.RED.value}{status}{colors.RESET.value}"
        else:
            status_colored = status 

        summary_table.append([
            scenario_name,
            fmt_num(r.dcf.enterprise_value / 1e9) + " B", 
            fmt_num(intrinsic),
            fmt_num(r.dcf.pv_fcfs_total),
            fmt_num(r.dcf.terminal_value),
            fmt_num(r.dcf.pv_terminal_value),
            fmt_pct(r.implied_wacc),
            status_colored,
        ])

    return summary_table


def build_growth_rate_table(report: DCFValuationReport) -> List[List[str]]:
    return [
        [scenario_name] + [fmt_pct(g) for g in r.growth_rates]
        for scenario_name, r in report.scenarios.items()
    ]


def _build_projection_table(report: DCFValuationReport, projection_attr: str, value_attr: str) -> List[List[str]]:
    data_table = []

    for scenario_name, r in report.scenarios.items():
        if projection_attr == 'dcf':
            proj = getattr(r.dcf, value_attr, [])
        else:
            proj = getattr(r, value_attr, [])
            
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None

        data_table.append(
            [scenario_name] + [fmt_num(v) for v in proj] + [fmt_pct(total_growth)]
        )
    return data_table


def build_fcf_projection_table(report: DCFValuationReport) -> List[List[str]]:
    return _build_projection_table(report, 'result', 'fcf_projections')


def build_pv_fcf_table(report: DCFValuationReport) -> List[List[str]]:
    return _build_projection_table(report, 'dcf', 'pv_fcfs')



def cli_print_valuation(
    metrics: StockMetrics,
    report: DCFValuationReport
):
    ticker = metrics.profile.ticker
    current_price = metrics.market_data.current_price
    pe_ratio = metrics.market_data.pe_ttm
    
    if not report.scenarios:
        print(f"ERROR: DCFValuationReport for {ticker} contains no scenarios.")
        return

    first_result = next(iter(report.scenarios.values()))


    print(f"====================== DCF Valuation Comparison for {ticker} ======================\n")

    summary_info = build_summary_metrics_table(current_price, pe_ratio, report) 
    print(tabulate(summary_info, headers=["Metric", "Value"], tablefmt="fancy_grid"))
    print()

    summary_headers = [
        "Scenario", "Enterprise Value", "Intrinsic Value/Share",
        "Total PV FCFs", "Terminal Value", "PV Terminal Value", "Implied WACC",
        "Status" 
    ]
    summary_table = build_scenario_summary_table(report)
    print(tabulate(summary_table, headers=summary_headers, tablefmt="fancy_grid"))

    print("\n-- Growth Rate Comparison by Scenario --")
    num_growth_years = len(first_result.growth_rates)
    growth_headers = ["Scenario"] + [f"Year {i+1}" for i in range(num_growth_years)]
    growth_table = build_growth_rate_table(report)
    print(tabulate(growth_table, headers=growth_headers, tablefmt="fancy_grid"))

    print("\n-- Free Cash Flow Projections by Scenario --")
    proj_len = len(first_result.fcf_projections)
    fcf_headers = ["Scenario"] + [f"Year {i+1}" for i in range(proj_len)] + ["Total Growth"]
    fcf_table = build_fcf_projection_table(report)
    print(tabulate(fcf_table, headers=fcf_headers, tablefmt="fancy_grid"))

    print("\n-- Present Value of Each FCF by Scenario --")
    pv_len = len(first_result.dcf.pv_fcfs)
    pv_headers = ["Scenario"] + [f"Year {i+1}" for i in range(pv_len)] + ["Total Growth"]
    pv_table = build_pv_fcf_table(report)
    print(tabulate(pv_table, headers=pv_headers, tablefmt="fancy_grid"))
    print()