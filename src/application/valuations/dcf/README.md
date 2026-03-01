# Discounted Cash Flow (DCF) Valuation Model – Formula Reference

This document explains the financial formulas used in the DCF valuation script, including how future cash flows are discounted, how terminal value is calculated, and how intrinsic value per share is derived. It also explains the WACC and CAPM formulas used to determine the appropriate discount rate.

---

## 1. Present Value of a Future Cash Flow

**Formula:**

\[
PV = \frac{FCF_t}{(1 + r)^t}
\]

Where:
| Symbol | Meaning |
|--------|---------|
| \( FCF_t \) | Free Cash Flow in year *t* |
| \( r \) | Discount rate (WACC or cost of equity) |
| \( t \) | Number of years in the future |

**Purpose:**  
Money today is worth more than the same amount in the future.  
This formula adjusts future cash flows to today’s value.

---

## 2. Present Value of Free Cash Flows (Total)

We project Free Cash Flow for several future years and then discount each of them.

**Formula:**

\[
PV_{FCFs} = \sum_{t=1}^{N} \frac{FCF_t}{(1 + r)^t}
\]

Where:
- \(N\) = Number of projected years

This sum represents the **value of the company’s projected operations before the terminal period**.

---

## 3. Terminal Value Using the Gordon Growth Model

After the projection period, we assume the company grows at a stable perpetual rate.

**Formula:**

\[
TV = \frac{FCF_{last} \cdot (1 + g)}{r - g}
\]

Where:
| Symbol | Meaning |
|--------|---------|
| \( FCF_{last} \) | Final projected year’s free cash flow |
| \( g \) | Perpetual long-term growth rate |
| \( r \) | Discount rate |

This represents the value of all future cash flows **beyond the projection window**.

---

## 4. Present Value of Terminal Value

Because terminal value occurs in the future, it also must be discounted:

\[
PV_{TV} = \frac{TV}{(1 + r)^N}
\]

Where:
- \(N\) = Number of projected years

---

## 5. Enterprise Value and Intrinsic Share Value

\[
Enterprise\ Value = PV_{FCFs} + PV_{TV}
\]

\[
Intrinsic\ Value\ Per\ Share = \frac{Enterprise\ Value}{Shares\ Outstanding}
\]

This final per-share value is compared to the current market price to determine valuation.

---

## 6. Cost of Equity (CAPM)

To determine the discount rate, we calculate **Cost of Equity** using the **Capital Asset Pricing Model**:

\[
Re = Rf + \beta (Market\ Risk\ Premium)
\]

Where:
| Symbol | Meaning |
|--------|---------|
| \( Re \) | Cost of equity |
| \( Rf \) | Risk-free rate (e.g., 10-Year U.S. Treasury yield) |
| \( \beta \) | Company's beta (stock's volatility relative to the market) |
| Market Risk Premium | Expected return of market over \( Rf \) |

---

## 7. Weighted Average Cost of Capital (WACC)

WACC represents the blended cost of financing (debt + equity):

\[
WACC = \left(\frac{E}{V}\right) Re + \left(\frac{D}{V}\right) Rd (1 - T)
\]

Where:
| Symbol | Meaning |
|--------|---------|
| \(E\) | Market value of equity (Market Cap) |
| \(D\) | Market value of debt |
| \(V = E + D\) | Total firm value |
| \(Re\) | Cost of equity (from CAPM) |
| \(Rd\) | Cost of debt (interest expense / debt) |
| \(T\) | Corporate tax rate |

WACC is typically used as the discount rate in DCF.

---

## Summary

| Step | Concept | Formula Output |
|------|---------|----------------|
| 1 | Discount future FCFs | Present Value of each FCF |
| 2 | Sum discounted FCFs | PV of projected operating value |
| 3 | Calculate terminal value | Long-term business value |
| 4 | Discount terminal value | Present Value of future terminal value |
| 5 | Add everything and divide by shares | Intrinsic Value per Share |

---

This model provides a structured and theoretically grounded way to estimate whether a stock is **undervalued**, **overvalued**, or **reasonably priced** based on expected future profitability rather than market sentiment.

