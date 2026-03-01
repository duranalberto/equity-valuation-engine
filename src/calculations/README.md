# Calculations Module Overview

This module provides a clean, modular, and maintainable set of financial calculation utilities. Functions are organized into subpackages covering DCF modelling, fundamental accounting ratios, and enterprise value analysis. All modules contain pure computational logic with no data fetching.

---

## Directory Structure

```
calculations/
│
├── dcf/
│   ├── core_calculations.py
│   ├── present_value.py
│   ├── terminal_value.py
│   ├── cost_of_capital.py
│   └── market_ev.py
│
├── fundamentals/
│   ├── cash_flow.py
│   ├── tax_debt_metrics.py
│   ├── margins.py
│   ├── growth_valuation.py
│   ├── balance_sheet.py
│   ├── return_metrics.py
│   └── dividend_ratios.py
│
├── enterprise_value/
│   ├── enterprise_value_core.py
│   └── ev_multiples.py
│
└── utils.py
```

---

## Module Descriptions

### **calculations/**

#### **utils.py**

* `safe_div(...)` – Performs safe numeric division with zero-handling.

---

### **calculations/dcf/**

Modules supporting Discounted Cash Flow (DCF) modelling.

#### **core_calculations.py**

* `enterprise_value(...)` – Computes enterprise value from discounted cash flows and terminal value.
* `intrinsic_value_per_share(...)` – Calculates intrinsic per-share valuation.

#### **present_value.py**

* `discount_to_present(...)` – Discounts a future cash flow to present value.
* `present_value_of_fcfs(...)` – Discounts a stream of projected free cash flows.

#### **terminal_value.py**

* `terminal_value_gordon(...)` – Computes terminal value using the Gordon Growth Model.

#### **cost_of_capital.py**

* `cost_of_equity_capm(...)` – Computes cost of equity using the CAPM formula.
* `market_implied_wacc(...)` – Reverse-engineers discount rate (WACC) to match observed market EV via numerical search.

#### **market_ev.py**

* `market_enterprise_value(...)` – Computes enterprise value from market capitalization, debt, and cash.
* `equity_weight(...)` – Determines equity share in capital structure.
* `debt_weight(...)` – Determines debt share in capital structure.
* `waac(...)` – Computes weighted average cost of capital (WACC). If this is intended to be `wacc`, ensure naming consistency in code.

---

### **calculations/fundamentals/**

Core fundamental accounting and financial ratio analysis.

#### **cash_flow.py**

* `fcf_ttm(...)` – Computes trailing twelve-month free cash flow.
* `last_fcf(...)` – Computes the most recent free cash flow figure.

#### **tax_debt_metrics.py**

* `effective_tax_rate_ttm(...)` – Calculates effective trailing tax rate.
* `cost_of_debt(...)` – Computes cost of debt using interest and debt levels.
* `roic(...)` – Computes return on invested capital.

#### **margins.py**

* `gross_margin(...)` – Gross profit margin.
* `operating_margin(...)` – Operating margin.
* `net_margin(...)` – Net profit margin.
* `ebit_margin(...)` – EBIT margin.
* `fcf_margin(...)` – Free cash flow margin.

#### **growth_valuation.py**

* `peg_ratio(...)` – Computes the price/earnings-to-growth ratio.
* `price_to_sales(...)` – Price-to-sales valuation multiple.
* `price_to_book(...)` – Price-to-book valuation multiple.
* `cagr_from_series(...)` - Computes CAGR from a sequence of EPS.
* `median_pe_ratio(...)` - Computes the median historical P/E ratio.

#### **balance_sheet.py**

* `current_ratio(...)` – Short‑term liquidity ratio.
* `quick_ratio(...)` – Acid‑test liquidity ratio.

#### **return_metrics.py**

* `return_on_equity(...)` – Measures profitability relative to equity.
* `return_on_assets(...)` – Measures profitability relative to total assets.

#### **dividend_ratios.py**

* `dividend_yield(...)` – Dividend yield based on price.
* `payout_ratio(...)` – Fraction of earnings paid as dividends.

---

### **calculations/enterprise_value/**

Enterprise value construction and valuation multiples.

#### **enterprise_value_core.py**

* `enterprise_value(...)` – Computes enterprise value from market capitalization, debt, and cash.

#### **ev_multiples.py**

* `ev_ebitda(...)` – EV/EBITDA valuation multiple.
* `ev_ebit(...)` – EV/EBIT valuation multiple.
* `fcf_yield(...)` – Free cash flow yield relative to enterprise value.
* `debt_to_equity(...)` – Measures leverage based on debt-to-equity.
* `interest_coverage(...)` – EBIT-to-interest expense ratio.
* `price_to_fcf(...)` – Price-to-free-cash-flow valuation multiple.

---

## Purpose of the Structure

* Reinforces a clear separation of financial modelling domains.
* Ensures maintainability, modular expansion, and robust unit test coverage.
* Provides a professional taxonomy aligned with standard valuation and accounting frameworks.
* Establishes a reliable foundation for future analytical extensions and modelling automation.
