"""Unit tests for analysis/discover.py — drift, sparkline, and scan_ticker."""

from unittest.mock import patch

import pandas as pd
import pytest

from analysis.discover import compute_drift_5d, compute_sparkline, scan_ticker


# ---------------------------------------------------------------------------
# compute_drift_5d
# ---------------------------------------------------------------------------

class TestComputeDrift5d:
    def test_uses_last_6_closes_when_available(self):
        # 10 closes; closes[-6] = closes[4] = 102, closes[-1] = 150
        closes = [90, 95, 98, 100, 102, 100, 105, 110, 120, 150]
        result = compute_drift_5d(closes)
        assert result == pytest.approx((150 - 102) / 102)

    def test_falls_back_to_full_range_when_fewer_than_6(self):
        closes = [80, 100]
        result = compute_drift_5d(closes)
        assert result == pytest.approx((100 - 80) / 80)

    def test_returns_zero_for_single_close(self):
        assert compute_drift_5d([100]) == 0.0

    def test_returns_zero_for_empty_list(self):
        assert compute_drift_5d([]) == 0.0

    def test_negative_drift(self):
        closes = [120, 110, 105, 100, 95, 90, 85]
        # -6 index is closes[1] = 110, last is 85
        result = compute_drift_5d(closes)
        assert result == pytest.approx((85 - 110) / 110)

    def test_exactly_6_closes(self):
        closes = [100, 101, 102, 103, 104, 110]
        result = compute_drift_5d(closes)
        assert result == pytest.approx((110 - 100) / 100)


# ---------------------------------------------------------------------------
# compute_sparkline
# ---------------------------------------------------------------------------

class TestComputeSparkline:
    def test_returns_last_14_from_longer_series(self):
        closes = list(range(1, 21))  # 1..20
        result = compute_sparkline(closes)
        assert result == list(range(7, 21))
        assert len(result) == 14

    def test_returns_all_when_fewer_than_14(self):
        closes = [10.0, 11.0, 12.0]
        result = compute_sparkline(closes)
        assert result == closes

    def test_returns_empty_for_empty_input(self):
        assert compute_sparkline([]) == []

    def test_custom_n(self):
        closes = list(range(1, 11))  # 1..10
        result = compute_sparkline(closes, n=5)
        assert result == [6, 7, 8, 9, 10]

    def test_exactly_14_closes(self):
        closes = list(range(14))
        result = compute_sparkline(closes)
        assert result == closes


# ---------------------------------------------------------------------------
# scan_ticker — per-ticker fail-safe: one bad ticker must degrade, not raise,
# so /discover can still return results for the rest of the watchlist.
# ---------------------------------------------------------------------------

class TestScanTicker:
    @patch("analysis.discover.get_company_name", return_value="Apple Inc.")
    @patch("analysis.discover.get_signal")
    @patch("analysis.discover.get_summary")
    @patch("analysis.discover.add_volume_signal", side_effect=lambda df: df)
    @patch("analysis.discover.add_moving_averages", side_effect=lambda df, windows: df)
    @patch("analysis.discover.get_stock_data")
    def test_success_returns_full_result(
        self, mock_fetch, _mock_ma, _mock_vol, mock_summary, mock_signal, _mock_name
    ):
        mock_fetch.return_value = pd.DataFrame({"Close": [100.0, 101.0, 105.0]})
        mock_summary.return_value = {"current_price": 105.0}
        mock_signal.return_value = {"signal": "BULLISH", "confidence": "High", "reasoning": "strong volume"}

        result = scan_ticker("AAPL", 30)

        assert result["ticker"] == "AAPL"
        assert result["company_name"] == "Apple Inc."
        assert result["signal"] == "BULLISH"
        assert result["confidence"] == "High"
        assert result["price"] == 105.0
        assert result["error"] is None
        assert result["_signal_obj"] == mock_signal.return_value

    @patch("analysis.discover.get_stock_data", side_effect=ConnectionError("yfinance unreachable"))
    def test_data_failure_degrades_gracefully_without_raising(self, _mock_fetch):
        """A network failure fetching price data must not propagate out of scan_ticker."""
        result = scan_ticker("AAPL", 30)

        assert result["ticker"] == "AAPL"
        assert result["company_name"] == "AAPL"
        assert result["signal"] == "ERROR"
        assert result["confidence"] == "—"
        assert result["price"] is None
        assert result["sparkline"] == []
        assert result["error"] == "yfinance unreachable"
        assert result["_signal_obj"] is None

    @patch("analysis.discover.get_signal", side_effect=RuntimeError("Anthropic API down"))
    @patch("analysis.discover.get_summary")
    @patch("analysis.discover.add_volume_signal", side_effect=lambda df: df)
    @patch("analysis.discover.add_moving_averages", side_effect=lambda df, windows: df)
    @patch("analysis.discover.get_stock_data")
    def test_ai_failure_isolated_to_this_ticker(
        self, mock_fetch, _mock_ma, _mock_vol, mock_summary, _mock_signal
    ):
        """An AI-signal failure on one ticker degrades that result instead of raising."""
        mock_fetch.return_value = pd.DataFrame({"Close": [100.0, 101.0]})
        mock_summary.return_value = {"current_price": 101.0}

        result = scan_ticker("AAPL", 30)

        assert result["signal"] == "ERROR"
        assert result["error"] == "Anthropic API down"