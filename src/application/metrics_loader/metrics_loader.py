"""
MetricsLoader — bridges the FinancialRepository and the domain model.

Changes from the original
--------------------------
1. ``loader_cls`` is validated as a ``FinancialRepository`` at construction
   time via ``isinstance`` (now possible because the protocol is
   ``@runtime_checkable``).

2. ``_build_valuation`` no longer calls phantom mapper keys
   (``cost_of_debt`` / ``corporate_tax_rate``) that the yfinance info dict
   never contains.  Those values are now derived inside ``Valuation.build``
   from statement data.  ``_build_valuation`` only passes the
   loader-specific seed that the domain cannot derive itself:
   ``highest_price``.

3. ``ValuationMapper`` entries for ``cost_of_debt`` and
   ``corporate_tax_rate`` are dead code and documented as such — they remain
   in the mapper for now so the mapper's field coverage validation still
   passes, but they are not used by this loader.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Type, Union

import domain.metrics.stock as sm
from infrastructure.repositories.financial_repository import (
    Action, BaseField, EnumField,
    FinancialField, LabelField, FinancialRepository,
)
from infrastructure.repositories import YfinanceDataLoader


class MetricsLoader:
    def __init__(
        self,
        ticker_symbol: str,
        loader_cls: Type = YfinanceDataLoader,
    ) -> None:
        loader_instance = loader_cls(ticker_symbol)
        if not isinstance(loader_instance, FinancialRepository):
            raise TypeError(
                f"{loader_cls.__name__} does not implement the "
                "FinancialRepository protocol.  Ensure it defines: "
                "get_label, get_ttm_from_quarters, get_annual_value, "
                "get_latest_numeric, get_highest_price, get_price_history, "
                "get_eps_history, get_eps_data_quality."
            )

        self.loader: FinancialRepository = loader_instance
        self.mapper = self.loader.mapper

    def get_latest_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        return self.loader.get_latest_numeric(field)

    def get_ttm_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        return self.loader.get_ttm_from_quarters(field, year_offset=0)

    def get_ttm_prev_value(self, field: FinancialField) -> Optional[float]:
        if field is None:
            return None
        prev_ttm = self.loader.get_ttm_from_quarters(field, year_offset=1)
        if prev_ttm is not None:
            return prev_ttm
        return self.loader.get_annual_value(field, year_offset=1)

    def get_from_field(
        self, field: BaseField
    ) -> Optional[Union[float, str, Enum]]:
        if isinstance(field, FinancialField):
            match field.action:
                case Action.GET_LATEST_VALUE:
                    return self.get_latest_value(field)
                case Action.GET_TTM_VALUE:
                    return self.get_ttm_value(field)
                case Action.GET_TTM_PREV_VALUE:
                    return self.get_ttm_prev_value(field)

        if isinstance(field, (LabelField, EnumField)):
            return self.loader.get_label(field)

        return None

    def _build_valuation(self) -> sm.Valuation:
        """
        Construct a seed ``Valuation`` for the loader-specific fields.

        Only ``highest_price`` is passed here — the value that the domain
        cannot derive from statement data alone.  ``cost_of_debt`` and
        ``corporate_tax_rate`` are intentionally omitted; ``Valuation.build``
        derives them from ``financials.interest_expense_ttm`` /
        ``balance_sheet.total_debt`` and ``financials.tax_expense_ttm`` /
        ``financials.ebt_ttm`` respectively.

        The ``ValuationMapper`` still declares ``cost_of_debt`` and
        ``corporate_tax_rate`` entries (pointing at yfinance info keys that
        don't exist) to satisfy the mapper's field-coverage validation.
        Those resolved values are deliberately ignored here.
        """
        return sm.Valuation(
            highest_price=self.loader.get_highest_price(),
            cost_of_debt=None,
            corporate_tax_rate=None,
            price_to_sales=None,
            price_to_book=None,
            median_historical_pe=None,
            fcf_cagr=None,
            forward_growth_rate=None,
            enterprise_value=None,
        )

    def _build_historical_data(self) -> sm.HistoricalData:
        return sm.HistoricalData(
            price_history=self.loader.get_price_history(),
            eps_history=self.loader.get_eps_history(),
        )

    def build_stock_metrics(self) -> sm.StockMetrics:
        return sm.StockMetrics(
            profile=self.build_model(sm.CompanyProfile),
            financials=self.build_model(sm.Financials),
            cash_flow=self.build_model(sm.CashFlow),
            balance_sheet=self.build_model(sm.BalanceSheet),
            ratios=None,
            market_data=self.build_model(sm.MarketData),
            valuation=self._build_valuation(),
            historical_data=self._build_historical_data(),
        )

    def build_model(self, model_cls: type) -> object:
        mapper = self.mapper[model_cls]
        kwargs = {}
        for field_name, field_def in mapper.items():
            if isinstance(field_def, BaseField):
                kwargs[field_name] = self.get_from_field(field_def)
            else:
                kwargs[field_name] = None
        return mapper.target_type(**kwargs)