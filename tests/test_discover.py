"""Unit tests for analysis/discover.py — drift and sparkline derivation."""

import pytest
from analysis.discover import compute_drift_5d, compute_sparkline


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