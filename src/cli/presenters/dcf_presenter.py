from tabulate import tabulate

from domain.metrics.stock import StockMetrics
from domain.valuation.models.dcf import (
    DCFSensitivityReport,
    DCFValuationReport,
    DCFValuationResult,
)

from .utils import colors, fmt_num, fmt_pct


def build_summary_metrics_table(current_price, pe_ratio, report):
    return [
        ["Current Stock Price", fmt_num(current_price)],
        ["P/E Ratio",           fmt_num(pe_ratio)],
        ["Cost of Equity",      fmt_pct(report.wacc.cost_of_equity)],
        ["WACC",                fmt_pct(report.wacc.wacc)],
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

        # BUG-E: annotate seed source in the enterprise value column
        seed_note = f" [{r.fcf_seed_source}]" if r.fcf_seed_source else ""

        summary_table.append([
            scenario_name,
            fmt_num(r.dcf.enterprise_value / 1e9) + " B" + seed_note,
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
        proj        = get_values(r)
        total_growth = (proj[-1] / proj[0] - 1) if proj and proj[0] != 0 else None
        data_table.append([scenario_name] + [fmt_num(v) for v in proj] + [fmt_pct(total_growth)])
    return data_table


def build_fcf_projection_table(report):
    return _build_projection_table(report, lambda r: r.fcf_projections)


def build_pv_fcf_table(report):
    return _build_projection_table(report, lambda r: r.dcf.pv_fcfs)


# BUG-E: new table — show TV seed per scenario
def build_tv_seed_table(report) -> list:
    """
    BUG-E: show the 3-year average FCF seed used for each scenario's terminal value.
    Highlights the discrepancy between year-N FCF in projections and the TV base.
    """
    rows = []
    for scenario_name, r in report.scenarios.items():
        tv_seed = getattr(r, "fcf_tv_seed", None)
        year_n  = r.fcf_projections[-1] if r.fcf_projections else None
        diff    = ((year_n - tv_seed) / tv_seed) if (year_n and tv_seed and tv_seed != 0) else None
        rows.append([
            scenario_name,
            fmt_num(tv_seed),
            fmt_num(year_n),
            fmt_pct(diff) if diff is not None else "—",
        ])
    return rows


def build_sensitivity_table(sens: DCFSensitivityReport) -> tuple[list, list]:
    tgr_headers = ["WACC \\ TGR"] + [fmt_pct(t) for t in sens.terminal_growth_values]

    rows = []
    wacc_indices = list(range(len(sens.wacc_values) - 1, -1, -1))
    for i in wacc_indices:
        wacc  = sens.wacc_values[i]
        label = fmt_pct(wacc)
        if abs(wacc - sens.base_wacc) < 1e-6:
            label += "*"
        row = [label]
        for j, tgr in enumerate(sens.terminal_growth_values):
            cell_val = sens.intrinsic_values[i][j]
            if cell_val is None:
                cell = "N/A"
            else:
                cell = fmt_num(cell_val)
                if abs(wacc - sens.base_wacc) < 1e-6 and abs(tgr - sens.base_terminal_growth) < 1e-6:
                    cell += "*"
            row.append(cell)
        rows.append(row)

    return tgr_headers, rows


def cli_print_valuation(metrics: StockMetrics, report: DCFValuationReport) -> None:
    ticker        = metrics.profile.ticker
    current_price = metrics.market_data.current_price
    pe_ratio      = metrics.market_data.pe_ttm

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
    growth_headers   = ["Scenario"] + [f"Year {i + 1}" for i in range(num_growth_years)]
    print(tabulate(build_growth_rate_table(report), headers=growth_headers, tablefmt="fancy_grid"))

    print("\n-- Free Cash Flow Projections by Scenario --")
    proj_len   = len(first_result.fcf_projections)
    fcf_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(proj_len)] + ["Total Growth"]
    print(tabulate(build_fcf_projection_table(report), headers=fcf_headers, tablefmt="fancy_grid"))

    print("\n-- Present Value of Each FCF by Scenario --")
    pv_len     = len(first_result.dcf.pv_fcfs)
    pv_headers = ["Scenario"] + [f"Year {i + 1}" for i in range(pv_len)] + ["Total Growth"]
    print(tabulate(build_pv_fcf_table(report), headers=pv_headers, tablefmt="fancy_grid"))

    # BUG-E: TV seed transparency table
    if any(getattr(r, "fcf_tv_seed", None) is not None for r in report.scenarios.values()):
        print("\n-- Terminal Value FCF Seed (3-yr avg) vs Year-N FCF --")
        print("   (TV seed is the 3-year average FCF used as the Gordon Growth base)")
        tv_headers = ["Scenario", "TV Seed (3yr avg)", "Year-N FCF", "Year-N vs Seed"]
        print(tabulate(build_tv_seed_table(report), headers=tv_headers, tablefmt="fancy_grid"))

    if report.sensitivity is not None:
        sens = report.sensitivity
        spread_note = ""
        # DESIGN-C: show derived spread info if available
        if sens.derived_wacc_spread is not None:
            spread_note = (
                f" (WACC spread={fmt_pct(sens.derived_wacc_spread)} derived from beta"
                f", TGR spread={fmt_pct(sens.derived_tgr_spread)} from sector)"
            )
        print(
            f"\n-- Intrinsic Value Sensitivity: WACC × Terminal Growth Rate "
            f"({sens.scenario_name} scenario FCFs){spread_note} --"
        )
        print(
            f"   (* marks base-case cell: WACC={fmt_pct(sens.base_wacc)}, "
            f"TGR={fmt_pct(sens.base_terminal_growth)})"
        )
        headers, rows = build_sensitivity_table(sens)
        print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print()