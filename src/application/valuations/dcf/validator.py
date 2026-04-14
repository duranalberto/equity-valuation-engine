from domain.metrics.stock import StockMetrics
from typing import List, Tuple, Union, Optional
from domain.valuation.policies import (
    ValuationChecker, CheckFactor, FactorSeverity, ValuationCheckResult,
)


class DCFChecker(ValuationChecker):

    CRITICAL_WEIGHT = 3
    WARNING_WEIGHT = 1

    def __init__(self, stock_metrics: StockMetrics):
        self._metrics = stock_metrics
        self._factors: List[CheckFactor] = []
        self._score = 0

    def _add_factor(self, name, message, severity, value=None):
        weight = (
            self.CRITICAL_WEIGHT if severity == FactorSeverity.CRITICAL
            else self.WARNING_WEIGHT if severity == FactorSeverity.WARNING
            else 0
        )
        self._factors.append(
            CheckFactor(name=name, message=message, severity=severity, weight=weight, value=value)
        )
        self._score += weight

    def _interpret_score(self) -> Tuple[bool, str]:
        score = self._score
        if score == 0:
            return True, "Perfectly suitable for DCF."
        elif 1 <= score <= 5:
            return True, "Minor warnings, generally suitable for DCF."
        elif 6 <= score <= 10:
            return False, "Moderate concerns, use DCF with caution."
        else:
            return False, "Significant risk, DCF may be unreliable."

    def _check_free_cash_flow(self):
        fcf_ttm = self._metrics.cash_flow.fcf_ttm
        last_quarter_fcf = self._metrics.cash_flow.last_quarter_fcf
        last_year_fcf = self._metrics.cash_flow.last_year_fcf

        if fcf_ttm is None:
            self._add_factor("Missing FCF (TTM)", "Free Cash Flow (TTM) data is missing.", FactorSeverity.CRITICAL)
        elif fcf_ttm < 0:
            message = f"Free Cash Flow (TTM) is negative: {fcf_ttm}"
            if last_quarter_fcf is not None and last_quarter_fcf > 0:
                self._add_factor("Negative TTM FCF (Temporary)", f"{message}, but last quarter FCF is positive, suggesting temporary cash burn.", FactorSeverity.WARNING, fcf_ttm)
            else:
                self._add_factor("Negative TTM FCF", message, FactorSeverity.CRITICAL, fcf_ttm)

        if last_year_fcf is None:
            self._add_factor("Missing Last Year FCF", "Last Year FCF data is missing.", FactorSeverity.CRITICAL)
        elif last_year_fcf < 0:
            self._add_factor("Negative Last Year FCF", f"Last Year FCF is negative: {last_year_fcf}", FactorSeverity.CRITICAL, last_year_fcf)

    def _check_profitability(self):
        eps_ttm = self._metrics.market_data.eps_ttm if self._metrics.market_data else None
        net_income_ttm = self._metrics.financials.net_income_ttm
        operating_cf_ttm = self._metrics.cash_flow.operating_cf_ttm

        if eps_ttm is None or eps_ttm <= 0:
            self._add_factor("Negative EPS (TTM)", f"Earnings Per Share (TTM) is zero or negative: {eps_ttm}", FactorSeverity.CRITICAL, eps_ttm)
        if net_income_ttm <= 0:
            self._add_factor("Negative Net Income (TTM)", f"Net Income (TTM) is zero or negative: {net_income_ttm}", FactorSeverity.CRITICAL, net_income_ttm)
        if operating_cf_ttm < 0:
            self._add_factor("Negative Operating CF", f"Operating Cash Flow (TTM) is negative: {operating_cf_ttm}", FactorSeverity.CRITICAL, operating_cf_ttm)

    def _check_risk_and_stability(self):
        market_data = self._metrics.market_data
        valuation = self._metrics.valuation

        cost_of_debt = valuation.cost_of_debt if valuation else None
        if cost_of_debt is not None and cost_of_debt > 0.2:
            self._add_factor("High Cost of Debt", f"Cost of Debt is very high (>{cost_of_debt:.1%}), increasing WACC risk.", FactorSeverity.CRITICAL, cost_of_debt)

        tax_rate = valuation.corporate_tax_rate if valuation else None
        if tax_rate is not None and tax_rate < 0:
            self._add_factor("Negative Tax Rate", f"Corporate Tax Rate is negative: {tax_rate}", FactorSeverity.WARNING, tax_rate)

        beta = market_data.beta if market_data else None
        if beta is not None and beta > 2:
            self._add_factor("High Beta", f"Stock Beta is high ({beta:.2f}), suggesting high volatility and uncertainty.", FactorSeverity.WARNING, beta)

        market_cap = market_data.market_cap if market_data else None
        if market_cap is not None and market_cap < 500_000_000:
            self._add_factor("Small Market Cap", f"Market cap is small ($ {market_cap:,.0f}), may lead to less reliable long-term forecasts.", FactorSeverity.WARNING, market_cap)

    def _check_growth_stage(self):
        revenue_growth_rate = self._metrics.financials.revenue_growth_rate
        net_income_ttm = self._metrics.financials.net_income_ttm

        if revenue_growth_rate is not None and revenue_growth_rate > 0.2 and net_income_ttm < 0:
            self._add_factor("Growth-Stage Startup", f"High revenue growth ({revenue_growth_rate * 100:.2f}%) with negative net income, indicating a potentially high-risk, high-growth startup phase.", FactorSeverity.WARNING, revenue_growth_rate)

    def evaluate(self) -> ValuationCheckResult:
        self._check_free_cash_flow()
        self._check_profitability()
        self._check_risk_and_stability()
        self._check_growth_stage()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )


def evaluate_dcf(stock_metrics: StockMetrics) -> ValuationCheckResult:
    return DCFChecker(stock_metrics).evaluate()
