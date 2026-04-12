from enum import Enum
from typing import Optional, Union, Type
import domain.metrics.stock as sm
from infrastructure.repositories.financial_repository import (
    Action, BaseField, EnumField,
    FinancialField, LabelField, FinancialRepository
)
from infrastructure.repositories import YfinanceDataLoader


class MetricsLoader:
    def __init__(
        self,
        ticker_symbol: str,
        loader_cls: Type[FinancialRepository] = YfinanceDataLoader,
    ):
        self.loader: FinancialRepository = loader_cls(ticker_symbol)
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

    def get_from_field(self, field: BaseField) -> Optional[Union[float, str, Enum]]:
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
        mapper = self.mapper[sm.StockMetrics.valuation]
        return sm.Valuation(
            highest_price=self.loader.get_highest_price(),
            cost_of_debt=self.get_from_field(mapper["cost_of_debt"]),
            corporate_tax_rate=self.get_from_field(mapper["corporate_tax_rate"]),
        )

    def _build_historical_data(self) -> sm.HistoricalData:
        return sm.HistoricalData(
            price_history=self.loader.get_price_history(),
            eps_history=self.loader.get_eps_history(),
        )

    def build_stock_metrics(self) -> sm.StockMetrics:
        return sm.StockMetrics(
            # Fix 3: previously `model = self.build_model` stored a bound-method
            # reference and then called model(cls), which worked but was
            # misleading — it looked like build_model returned a configuration
            # object rather than being the callable itself.  Now each section
            # calls self.build_model(cls) directly, which is unambiguous.
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