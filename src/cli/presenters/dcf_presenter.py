from tabulate import tabulate
from domain.valuation.models.dcf import DCFValuationResult, DCFValuationReport
from domain.metrics.stock import StockMetrics
from .utils import fmt_num, fmt_pct, colors
from typing import List


def build_summary_metrics_table(current_price, pe_ratio, report):
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["P/E Ratio", fmt_num(pe_ratio)],
        ["Cost of Equity", fmt_pct(report.wacc.cost_of_equity)],
        ["WACC", fmt_pct(report.wacc.wacc)],
    ]


def build_scenario_summary_table(report):
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
            scenario_name,
            fmt_num(r.dcf.enterprise_value / 1e9) + " B",
            fmt_num(r.intrinsic_value_per_share),
            fmt_num(r.dcf.pv_fcfs_total),
            fmt_num(r.dcf.terminal_value),
            fmt_num(r.dcf.pv_terminal_value),
            fmt_pct(r.implied_wacc),
            status_colored,
        ])
    return summary_table


def build_growth_rate_table(report):
    return [
        [scenario_name] + [fmt_pct(g) for g in r.growth_rates]
        for scenario_name, r in report.scenarios.items()
    ]


def _build_projection_table(report, get_values):
    data_table = []
    for scenario_name, r in report.scenarios.items():
        proj = get_values(r)
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None
        data_table.append([scenario_name] + [fmt_num(v) for v in proj] + [fmt_pct(total_growth)])
    return data_table


def build_fcf_projection_table(report):
    return _build_projection_table(report, lambda r: r.fcf_projections)


def build_pv_fcf_table(report):
    return _build_projection_table(report, lambda r: r.dcf.pv_fcfs)


def cli_print_valuation(metrics: StockMetrics, report: DCFValuationReport) -> None:
    ticker = metrics.profile.ticker
    current_price = metrics.market_data.current_price
    pe_ratio = metrics.market_data.pe_ttm

    if not report.scenarios:
        print(f"ERROR: DCFValuationReport for {ticker} contains no scenarios.")
        return

    first_result: DCFValuationResult = next(iter(report.scenarios.values()))

    print(f"====================== DCF Valuation Comparison for {ticker} ======================\n")

    summary_info = build_summary_metrics_table(current_price, pe_ratio, report)
    print(tabulate(summary_info, headers=["Metric", "Value"], tablefmt="fancy_grid"))
    print()

    summary_headers = [
        "Scenario", "Enterprise Value", "Intrinsic Value/Share",
        "Total PV FCFs", "Terminal Value", "PV Terminal Value", "Implied WACC", "Status",
    ]
    print(tabulate(build_scenario_summary_table(report), headers=summary_headers, tablefmt="fancy_grid"))

    print("\n-- Growth Rate Comparison by Scenario --")
    num_growth_years = len(first_result.growth_rates)
    growth_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(num_growth_years)]
    print(tabulate(build_growth_rate_table(report), headers=growth_headers, tablefmt="fancy_grid"))

    print("\n-- Free Cash Flow Projections by Scenario --")
    proj_len = len(first_result.fcf_projections)
    fcf_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(proj_len)] + ["Total Growth"]
    print(tabulate(build_fcf_projection_table(report), headers=fcf_headers, tablefmt="fancy_grid"))

    print("\n-- Present Value of Each FCF by Scenario --")
    pv_len = len(first_result.dcf.pv_fcfs)
    pv_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(pv_len)] + ["Total Growth"]
    print(tabulate(build_pv_fcf_table(report), headers=pv_headers, tablefmt="fancy_grid"))
    print()
