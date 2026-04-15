import pytest

from infrastructure.repositories.financial_repository import Action, Statement
from infrastructure.repositories.yfinance.mappers import (
    CurrencyType,
    YfPerShareFinancialField,
)
from infrastructure.repositories.yfinance.mappers.stock_metrics_mapper import (
    MarketDataMapper,
)


def test_market_data_eps_fields_are_per_share_fields() -> None:
    mapper = MarketDataMapper()

    eps_fields = (
        mapper.mapping[mapper.target_type.eps_ttm],
        mapper.mapping[mapper.target_type.last_quarter_eps],
        mapper.mapping[mapper.target_type.last_year_eps],
    )

    assert all(isinstance(field, YfPerShareFinancialField) for field in eps_fields)
    assert all(field.currency_type is CurrencyType.NONE for field in eps_fields)


def test_per_share_financial_field_rejects_currency_conversion() -> None:
    with pytest.raises(ValueError, match="CurrencyType.NONE"):
        YfPerShareFinancialField(
            label=["eps"],
            currency_type=CurrencyType.FINANCIAL,
            statement=Statement.INCOME,
            action=Action.GET_LATEST_VALUE,
        )
