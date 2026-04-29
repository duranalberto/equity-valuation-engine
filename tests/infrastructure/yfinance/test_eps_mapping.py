from __future__ import annotations

import pandas as pd
import pytest

from domain.metrics.stock import MarketData
from infrastructure.repositories.yfinance.mappers.common_constants import (
    INCOME_STMT_LABELS,
    INFO_LABELS,
)
from infrastructure.repositories.yfinance.mappers.stock_metrics_mapper import (
    build_stock_metrics_mapper,
)
from infrastructure.repositories.yfinance.mappers.yfinance_fields import YfLabelField
from infrastructure.repositories.yfinance.value_objects import RawTickerData
from infrastructure.repositories.yfinance.yfinance_fetcher import YfinanceFetcher
from infrastructure.repositories.yfinance.yfinance_parser import YfinanceParser


def test_market_data_eps_fields_are_label_fields_with_eps_keys() -> None:
    mapper = build_stock_metrics_mapper()[MarketData]

    eps_ttm_field = mapper["eps_ttm"]
    last_quarter_eps_field = mapper["last_quarter_eps"]
    last_year_eps_field = mapper["last_year_eps"]

    assert isinstance(eps_ttm_field, YfLabelField)
    assert isinstance(last_quarter_eps_field, YfLabelField)
    assert isinstance(last_year_eps_field, YfLabelField)
    assert eps_ttm_field.label == INFO_LABELS["eps_ttm"]
    assert last_quarter_eps_field.label == INFO_LABELS["last_quarter_eps"]
    assert last_year_eps_field.label == INFO_LABELS["last_year_eps"]


def test_parser_derives_period_eps_from_net_income_per_share() -> None:
    net_income_label = INCOME_STMT_LABELS["net_income"][0]
    raw = RawTickerData(
        ticker="TEST",
        info={"sharesOutstanding": 10},
        income_stmt_q=pd.DataFrame(
            [[130.0, 120.0, 110.0, 100.0]],
            index=[net_income_label],
        ),
        income_stmt_a=pd.DataFrame(
            [[1000.0, 900.0, 800.0]],
            index=[net_income_label],
        ),
    )
    parser = YfinanceParser(YfinanceFetcher(raw))

    assert parser.last_quarter_eps() == pytest.approx(13.0)
    assert parser.last_year_eps() == pytest.approx(100.0)
