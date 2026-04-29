import pytest

from domain.metrics.stock import MarketData


@pytest.mark.parametrize("shares_outstanding", [None, 0, -1])
def test_market_data_rejects_non_positive_shares_outstanding(shares_outstanding) -> None:
    with pytest.raises(ValueError, match="shares_outstanding must be a positive integer"):
        MarketData(
            current_price=100.0,
            shares_outstanding=shares_outstanding,
            market_cap=1_000_000.0,
            beta=None,
            eps_ttm=None,
            pe_ttm=None,
            last_quarter_eps=None,
            last_year_eps=None,
            low_52_week=None,
            high_52_week=None,
            fifty_day_avg=None,
            two_hundred_day_avg=None,
            volume=None,
            avg_volume=None,
        )
