"""
tests/unit/fixtures.py

Deterministic StockMetrics stubs for ORCL, ADBE, and AI (C3.ai).
Values are taken directly from the terminal JSON output shown in the
implementation plan audit, so tests are stable and independent of yfinance.

These fixtures are imported by:
  tests/test_bug_a_dcf_validator.py
  tests/test_bug_b_roe_buyback.py
  tests/test_bug_c_roe_cap.py
  tests/test_bug_d_g_growth_signals.py
  tests/test_phase2_*.py
"""
from __future__ import annotations

from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Minimal dataclass-compatible namespace builders
# We use SimpleNamespace so the fixtures don't depend on the live domain
# model, which means they survive domain refactors without breaking.
# ---------------------------------------------------------------------------

def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# ORCL — Oracle Corporation
# Source: terminal JSON from implementation plan (ORCL run)
# ---------------------------------------------------------------------------

def make_orcl_metrics():
    financials = _ns(
        revenue_ttm=64_077_000_000.0,
        ebit_ttm=22_475_000_000.0,
        ebt_ttm=18_337_000_000.0,
        tax_expense_ttm=2_127_000_000.0,
        interest_expense_ttm=4_138_000_000.0,
        gross_profit_ttm=42_986_000_000.0,
        operating_income_ttm=20_678_000_000.0,
        net_income_ttm=16_210_000_000.0,
        revenue_ttm_prev=52_961_000_000.0,
        net_income_ttm_prev=10_467_000_000.0,
        da_ttm=8_143_000_000.0,
        revenue_growth_rate=0.2099,
        net_income_growth=0.5487,
        gross_margin=0.6708,
        operating_margin=0.3227,
        net_margin=0.2530,
        ebitda_ttm=30_618_000_000.0,
        history=_ns(
            net_income_annual=[6_717_000_000.0, 8_503_000_000.0,
                               10_467_000_000.0, 12_443_000_000.0],
        ),
    )

    cash_flow = _ns(
        operating_cf_ttm=23_514_000_000.0,
        capex_ttm=-48_250_000_000.0,
        oper_cf_last_year=20_821_000_000.0,
        latest_annual_capex=-21_215_000_000.0,
        oper_cf_last_quarter=7_151_000_000.0,
        latest_quarter_capex=-18_635_000_000.0,
        dividends_paid_ttm=-5_688_000_000.0,
        share_buybacks_ttm=-356_000_000.0,
        fcf_ttm=-24_736_000_000.0,
        last_year_fcf=-394_000_000.0,
        last_quarter_fcf=-11_484_000_000.0,
        history=_ns(
            fcf_annual=[5_028_000_000.0, 8_470_000_000.0,
                        11_807_000_000.0, -394_000_000.0],
            capex_annual=[-4_511_000_000.0, -8_695_000_000.0,
                          -6_866_000_000.0, -21_215_000_000.0],
            operating_cf_annual=[9_539_000_000.0, 17_165_000_000.0,
                                  18_673_000_000.0, 20_821_000_000.0],
        ),
    )

    balance_sheet = _ns(
        total_debt=153_117_000_000.0,
        total_equity=38_495_000_000.0,
        cash_and_equivalents=38_455_000_000.0,
        total_assets=245_240_000_000.0,
        total_liabilities=206_189_000_000.0,
        current_assets=54_874_000_000.0,
        current_liabilities=40_737_000_000.0,
        inventory=0.0,
        current_ratio=1.347,
        quick_ratio=1.347,
        history=None,
    )

    market_data = _ns(
        current_price=165.96,
        shares_outstanding=2_876_046_000,
        market_cap=477_308_613_469.39,
        beta=1.597,
        eps_ttm=5.57,
        pe_ttm=29.7953,
        last_quarter_eps=1.2938,
        last_year_eps=4.3264,
        low_52_week=134.57,
        high_52_week=345.72,
        fifty_day_avg=154.87,
        two_hundred_day_avg=213.37,
        volume=30_265_732,
        avg_volume=30_114_963,
    )

    valuation = _ns(
        highest_price=325.76,
        cost_of_debt=0.027,
        corporate_tax_rate=0.116,
        price_to_sales=7.449,
        price_to_book=12.3992,
        median_historical_pe=21.9091,
        fcf_cagr=0.0,
        forward_growth_rate=0.2281,
        enterprise_value=591_970_613_469.39,
        normalized_fcf=16_648_000_000.0,   # BUG-A: positive normalised FCF
        capex_spike_detected=True,          # BUG-A: capex spike flag
    )

    ratios = _ns(
        fcf_margin=-0.386,
        price_to_fcf=-19.2961,
        roic=0.1297,
        fcf_yield=-0.0518,
        debt_to_equity=3.9776,
        ebit_margin=0.3507,
        peg_ratio=54.304,
        peg_growth_source="ttm_ni_growth",
        return_on_equity=0.4211,           # BUG-C: exceeds technology cap of 0.35
        return_on_assets=0.0661,
        price_to_sales=7.449,
        price_to_book=12.3992,
        dividend_yield=0.0119,
        payout_ratio=0.3509,
        ev_ebit=26.3391,
        ev_ebitda=19.3341,
        book_value_per_share=13.3847,
        interest_coverage=5.4314,
        buyback_yield=0.0007,
        total_shareholder_yield=0.0127,
    )

    profile = _ns(
        ticker="ORCL",
        company_name="Oracle Corporation",
        sector=_make_sector("technology"),
        industry="Software - Infrastructure",
        country="United States",
        financial_currency="USD",
        trading_currency="USD",
        exchange="NYQ",
        quote_type="EQUITY",
        website="https://www.oracle.com",
    )

    return _ns(
        profile=profile,
        financials=financials,
        cash_flow=cash_flow,
        balance_sheet=balance_sheet,
        market_data=market_data,
        valuation=valuation,
        ratios=ratios,
        historical_data=None,
        _diagnostics=[],
    )


# ---------------------------------------------------------------------------
# ADBE — Adobe Inc.
# ---------------------------------------------------------------------------

def make_adbe_metrics():
    financials = _ns(
        revenue_ttm=24_453_000_000.0,
        ebit_ttm=9_238_000_000.0,
        ebt_ttm=8_974_000_000.0,
        tax_expense_ttm=1_766_000_000.0,
        interest_expense_ttm=264_000_000.0,
        gross_profit_ttm=21_860_000_000.0,
        operating_income_ttm=8_961_000_000.0,
        net_income_ttm=7_208_000_000.0,
        revenue_ttm_prev=21_505_000_000.0,
        net_income_ttm_prev=5_560_000_000.0,
        da_ttm=775_000_000.0,
        revenue_growth_rate=0.1371,
        net_income_growth=0.2964,
        gross_margin=0.894,
        operating_margin=0.3665,
        net_margin=0.2948,
        ebitda_ttm=10_013_000_000.0,
        history=_ns(
            net_income_annual=[4_756_000_000.0, 5_428_000_000.0,
                               5_560_000_000.0, 7_130_000_000.0],
        ),
    )

    cash_flow = _ns(
        operating_cf_ttm=10_507_000_000.0,
        capex_ttm=-190_000_000.0,
        oper_cf_last_year=10_031_000_000.0,
        latest_annual_capex=-179_000_000.0,
        oper_cf_last_quarter=2_958_000_000.0,
        latest_quarter_capex=-37_000_000.0,
        dividends_paid_ttm=0.0,            # BUG-B: zero dividends
        share_buybacks_ttm=-10_509_000_000.0,  # BUG-B: large buybacks
        fcf_ttm=10_317_000_000.0,
        last_year_fcf=9_852_000_000.0,
        last_quarter_fcf=2_921_000_000.0,
        history=_ns(
            fcf_annual=[7_396_000_000.0, 6_942_000_000.0,
                        7_873_000_000.0, 9_852_000_000.0],
            capex_annual=[-442_000_000.0, -360_000_000.0,
                          -183_000_000.0, -179_000_000.0],
            operating_cf_annual=[7_838_000_000.0, 7_302_000_000.0,
                                  8_056_000_000.0, 10_031_000_000.0],
        ),
    )

    balance_sheet = _ns(
        total_debt=6_656_000_000.0,
        total_equity=11_433_000_000.0,
        cash_and_equivalents=6_332_000_000.0,
        total_assets=29_704_000_000.0,
        total_liabilities=18_271_000_000.0,
        current_assets=10_386_000_000.0,
        current_liabilities=11_390_000_000.0,
        inventory=0.0,
        current_ratio=0.9119,
        quick_ratio=0.9119,
        history=None,
    )

    market_data = _ns(
        current_price=243.2,
        shares_outstanding=404_200_000,
        market_cap=98_301_438_766.48,
        beta=1.518,
        eps_ttm=17.17,
        pe_ttm=14.1642,
        last_quarter_eps=4.6734,
        last_year_eps=17.6398,
        low_52_week=224.13,
        high_52_week=422.95,
        fifty_day_avg=251.37,
        two_hundred_day_avg=316.01,
        volume=6_061_811,
        avg_volume=6_051_086,
    )

    valuation = _ns(
        highest_price=688.37,
        cost_of_debt=0.0397,
        corporate_tax_rate=0.1968,
        price_to_sales=4.02,
        price_to_book=8.598,
        median_historical_pe=37.2272,
        fcf_cagr=0.1003,
        forward_growth_rate=0.1445,
        enterprise_value=98_625_438_766.48,
        normalized_fcf=None,
        capex_spike_detected=False,
    )

    ratios = _ns(
        fcf_margin=0.4219,
        price_to_fcf=9.5281,
        roic=0.6311,
        fcf_yield=0.105,
        debt_to_equity=0.5822,
        ebit_margin=0.3778,
        peg_ratio=47.7871,
        peg_growth_source="ttm_ni_growth",
        return_on_equity=0.6305,           # BUG-C: exceeds technology cap of 0.35
        return_on_assets=0.2427,
        price_to_sales=4.02,
        price_to_book=8.598,
        dividend_yield=0.0,
        payout_ratio=0.0,
        ev_ebit=10.6761,
        ev_ebitda=9.8497,
        book_value_per_share=28.2855,
        interest_coverage=34.9924,
        buyback_yield=0.1069,
        total_shareholder_yield=0.1069,
    )

    profile = _ns(
        ticker="ADBE",
        company_name="Adobe Inc.",
        sector=_make_sector("technology"),
        industry="Software - Application",
        country="United States",
        financial_currency="USD",
        trading_currency="USD",
        exchange="NMS",
        quote_type="EQUITY",
        website="https://www.adobe.com",
    )

    return _ns(
        profile=profile,
        financials=financials,
        cash_flow=cash_flow,
        balance_sheet=balance_sheet,
        market_data=market_data,
        valuation=valuation,
        ratios=ratios,
        historical_data=None,
        _diagnostics=[],
    )


# ---------------------------------------------------------------------------
# AI — C3.ai, Inc.
# ---------------------------------------------------------------------------

def make_ai_metrics():
    financials = _ns(
        revenue_ttm=307_391_000.0,
        ebit_ttm=-466_305_000.0,
        ebt_ttm=-433_680_000.0,
        tax_expense_ttm=822_000.0,
        interest_expense_ttm=30_406_000.0,
        gross_profit_ttm=133_569_000.0,
        operating_income_ttm=-466_305_000.0,
        net_income_ttm=-434_502_000.0,      # NEGATIVE — BUG-G trigger
        revenue_ttm_prev=310_582_000.0,
        net_income_ttm_prev=-279_696_000.0,
        da_ttm=13_606_000.0,
        revenue_growth_rate=-0.0103,
        net_income_growth=0.5535,           # BUG-G: ratio of two negatives
        gross_margin=0.4345,
        operating_margin=-1.517,
        net_margin=-1.4135,
        ebitda_ttm=-452_699_000.0,
        history=_ns(
            net_income_annual=[-192_065_000.0, -268_839_000.0,
                               -279_696_000.0, -288_702_000.0],
        ),
    )

    cash_flow = _ns(
        operating_cf_ttm=-124_524_000.0,
        capex_ttm=-2_523_000.0,
        oper_cf_last_year=-41_407_000.0,
        latest_annual_capex=-3_039_000.0,
        oper_cf_last_quarter=-55_757_000.0,
        latest_quarter_capex=-439_000.0,
        dividends_paid_ttm=0.0,
        share_buybacks_ttm=0.0,
        fcf_ttm=-127_047_000.0,            # BUG-A trigger: dual-negative
        last_year_fcf=-44_446_000.0,       # BUG-A trigger: dual-negative
        last_quarter_fcf=-56_196_000.0,
        history=_ns(
            fcf_annual=[-90_753_000.0, -187_209_000.0,
                        -90_368_000.0, -44_446_000.0],
            capex_annual=[-4_291_000.0, -71_518_000.0,
                          -28_006_000.0, -3_039_000.0],
            operating_cf_annual=[-86_462_000.0, -115_691_000.0,
                                  -62_362_000.0, -41_407_000.0],
        ),
    )

    balance_sheet = _ns(
        total_debt=5_373_000.0,
        total_equity=719_473_000.0,
        cash_and_equivalents=88_847_000.0,
        total_assets=895_776_000.0,
        total_liabilities=176_303_000.0,
        current_assets=782_695_000.0,
        current_liabilities=118_935_000.0,
        inventory=0.0,
        current_ratio=6.5809,
        quick_ratio=6.5809,
        history=None,
    )

    market_data = _ns(
        current_price=8.97,
        shares_outstanding=145_291_222,
        market_cap=1_303_262_300.14,
        beta=2.07,
        eps_ttm=-3.16,
        pe_ttm=None,                       # negative EPS → no P/E
        last_quarter_eps=-0.9179,
        last_year_eps=-1.9871,
        low_52_week=7.675,
        high_52_week=30.24,
        fifty_day_avg=8.97,
        two_hundred_day_avg=14.86,
        volume=6_645_567,
        avg_volume=6_324_995,
    )

    valuation = _ns(
        highest_price=76.15,
        cost_of_debt=0.0,
        corporate_tax_rate=-0.0019,
        price_to_sales=4.2398,
        price_to_book=1.8114,
        median_historical_pe=None,
        fcf_cagr=-0.2118,
        forward_growth_rate=0.1455,
        enterprise_value=1_219_788_300.14,
        normalized_fcf=None,               # BUG-A: no normalised FCF for AI
        capex_spike_detected=False,
    )

    ratios = _ns(
        fcf_margin=-0.4133,
        price_to_fcf=-10.2581,
        roic=-0.7346,
        fcf_yield=-0.0975,
        debt_to_equity=0.0075,
        ebit_margin=-1.517,
        peg_ratio=0.0,
        peg_growth_source="",
        return_on_equity=-0.6039,          # NEGATIVE ROE → ROE model blocked
        return_on_assets=-0.4851,
        price_to_sales=4.2398,
        price_to_book=1.8114,
        dividend_yield=0.0,
        payout_ratio=0.0,
        ev_ebit=-2.6159,
        ev_ebitda=-2.6945,
        book_value_per_share=4.9519,
        interest_coverage=-15.336,
        buyback_yield=0.0,
        total_shareholder_yield=0.0,
    )

    profile = _ns(
        ticker="AI",
        company_name="C3.ai, Inc.",
        sector=_make_sector("technology"),
        industry="Software - Infrastructure",
        country="United States",
        financial_currency="USD",
        trading_currency="USD",
        exchange="NYQ",
        quote_type="EQUITY",
        website="https://www.c3.ai",
    )

    return _ns(
        profile=profile,
        financials=financials,
        cash_flow=cash_flow,
        balance_sheet=balance_sheet,
        market_data=market_data,
        valuation=valuation,
        ratios=ratios,
        historical_data=None,
        _diagnostics=[],
    )


# ---------------------------------------------------------------------------
# Helper — create a minimal Sectors-enum-compatible object from a string
# ---------------------------------------------------------------------------

def _make_sector(value: str):
    """
    Return a minimal sector stub whose .value attribute matches the string
    used in YAML configs.  Avoids a hard import of domain.core.enums.Sectors
    so fixtures stay importable even when domain code is being refactored.
    """
    return SimpleNamespace(value=value)