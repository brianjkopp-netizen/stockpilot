"""Tests for analysis.indicators — all tests use synthetic DataFrames, no network calls."""

import pandas as pd
import pytest
from unittest.mock import patch

from analysis.indicators import add_moving_averages, add_volume_signal, build_analysis_summary, get_summary


def make_df(close_prices: list[float], volumes: list[int]) -> pd.DataFrame:
    """Build a minimal OHLCV-shaped DataFrame with a DatetimeIndex."""
    index = pd.date_range(start="2026-01-01", periods=len(close_prices), freq="D")
    return pd.DataFrame({"Close": close_prices, "Volume": volumes}, index=index)


# ---------------------------------------------------------------------------
# add_moving_averages
# ---------------------------------------------------------------------------

def test_add_moving_averages_adds_correct_columns():
    """Requested windows produce correctly named MA columns."""
    df = make_df([float(i) for i in range(1, 26)], [1_000] * 25)
    result = add_moving_averages(df, [10, 20])
    assert "MA_10" in result.columns
    assert "MA_20" in result.columns


def test_add_moving_averages_computes_correct_values():
    """MA values on the last row match the expected rolling mean."""
    prices = [float(i) for i in range(1, 26)]  # 1..25
    df = make_df(prices, [1_000] * 25)
    result = add_moving_averages(df, [10, 20])

    # Last 10 values: 16..25 → mean = 20.5
    assert result["MA_10"].iloc[-1] == pytest.approx(20.5)
    # Last 20 values: 6..25 → mean = 15.5
    assert result["MA_20"].iloc[-1] == pytest.approx(15.5)


def test_add_moving_averages_early_rows_are_nan():
    """Rows with fewer preceding rows than the window should be NaN."""
    df = make_df([float(i) for i in range(1, 26)], [1_000] * 25)
    result = add_moving_averages(df, [10, 20])

    assert pd.isna(result["MA_10"].iloc[8])   # row 9, needs 10
    assert pd.isna(result["MA_20"].iloc[18])  # row 19, needs 20


# ---------------------------------------------------------------------------
# add_volume_signal
# ---------------------------------------------------------------------------

def test_add_volume_signal_adds_column():
    """Volume_Above_Avg column is present after calling the function."""
    df = make_df([100.0] * 15, [1_000] * 15)
    result = add_volume_signal(df)
    assert "Volume_Above_Avg" in result.columns


def test_add_volume_signal_true_when_above_average():
    """Last row is True when its volume exceeds the 10-day rolling mean."""
    volumes = [1_000] * 14 + [9_000]  # spike on the last day
    df = make_df([100.0] * 15, volumes)
    result = add_volume_signal(df)
    assert result["Volume_Above_Avg"].iloc[-1] == True


def test_add_volume_signal_false_when_below_average():
    """Last row is False when its volume is below the 10-day rolling mean."""
    volumes = [9_000] * 14 + [1_000]  # drop on the last day
    df = make_df([100.0] * 15, volumes)
    result = add_volume_signal(df)
    assert result["Volume_Above_Avg"].iloc[-1] == False


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------

def _enriched_df(close_prices: list[float], volumes: list[int]) -> pd.DataFrame:
    """Return a DataFrame already passed through both indicator functions."""
    df = make_df(close_prices, volumes)
    df = add_moving_averages(df, [10, 20])
    df = add_volume_signal(df)
    return df


def test_get_summary_returns_all_keys():
    """Summary dict contains every key the AI analyst expects."""
    df = _enriched_df([float(i) for i in range(1, 26)], [1_000] * 25)
    summary = get_summary(df)
    assert set(summary.keys()) == {
        "current_price", "ma_10", "ma_20",
        "volume_signal", "price_vs_ma10", "price_vs_ma20",
    }


def test_get_summary_current_price_is_last_close():
    """current_price reflects the most recent Close, rounded to 2 decimal places."""
    prices = [float(i) for i in range(1, 26)]
    df = _enriched_df(prices, [1_000] * 25)
    assert get_summary(df)["current_price"] == pytest.approx(25.0)


def test_get_summary_price_above_both_mas():
    """price_vs_ma10 and price_vs_ma20 are ABOVE when price exceeds both averages."""
    # Prices ramp up sharply at the end so the last close beats both MAs
    prices = [10.0] * 20 + [100.0] * 5
    df = _enriched_df(prices, [1_000] * 25)
    summary = get_summary(df)
    assert summary["price_vs_ma10"] == "ABOVE"
    assert summary["price_vs_ma20"] == "ABOVE"


def test_get_summary_price_below_both_mas():
    """price_vs_ma10 and price_vs_ma20 are BELOW when price drops under both averages."""
    prices = [100.0] * 20 + [10.0] * 5
    df = _enriched_df(prices, [1_000] * 25)
    summary = get_summary(df)
    assert summary["price_vs_ma10"] == "BELOW"
    assert summary["price_vs_ma20"] == "BELOW"


def test_get_summary_volume_signal_above():
    """volume_signal is ABOVE AVERAGE when the last day's volume spikes."""
    prices = [float(i) for i in range(1, 26)]
    volumes = [1_000] * 24 + [9_000]
    df = _enriched_df(prices, volumes)
    assert get_summary(df)["volume_signal"] == "ABOVE AVERAGE"


def test_get_summary_volume_signal_below():
    """volume_signal is BELOW AVERAGE when the last day's volume drops."""
    prices = [float(i) for i in range(1, 26)]
    volumes = [9_000] * 24 + [1_000]
    df = _enriched_df(prices, volumes)
    assert get_summary(df)["volume_signal"] == "BELOW AVERAGE"


# ---------------------------------------------------------------------------
# build_analysis_summary
# ---------------------------------------------------------------------------

def test_build_analysis_summary_returns_summary_dict():
    """build_analysis_summary runs the full pipeline and returns a valid summary dict."""
    prices = [float(i) for i in range(1, 26)]
    volumes = [1_000] * 25
    mock_df = make_df(prices, volumes)

    with patch("analysis.indicators.get_stock_data", return_value=mock_df) as mock_fetch:
        result = build_analysis_summary("AAPL", days=30)

    mock_fetch.assert_called_once_with("AAPL", 30)
    assert set(result.keys()) == {
        "current_price", "ma_10", "ma_20",
        "volume_signal", "price_vs_ma10", "price_vs_ma20",
    }
    assert result["current_price"] == pytest.approx(25.0)


def test_build_analysis_summary_uses_10_and_20_day_windows():
    """build_analysis_summary always computes MA_10 and MA_20 — window selection lives here, not in callers."""
    prices = [float(i) for i in range(1, 26)]
    mock_df = make_df(prices, [1_000] * 25)

    with patch("analysis.indicators.get_stock_data", return_value=mock_df):
        result = build_analysis_summary("AAPL")

    assert result["ma_10"] == pytest.approx(20.5)   # mean of 16..25
    assert result["ma_20"] == pytest.approx(15.5)   # mean of 6..25
