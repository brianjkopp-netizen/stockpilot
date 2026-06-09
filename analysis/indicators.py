"""Technical indicator calculations for the StockPilot analysis pipeline."""

import pandas as pd


def add_moving_averages(df: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    """Add simple moving average columns to an OHLCV DataFrame.

    Args:
        df: OHLCV DataFrame with a DatetimeIndex and a Close column.
        windows: List of lookback periods in days, e.g. [10, 20].

    Returns:
        The input DataFrame with additional columns named MA_<window>
        (e.g. MA_10, MA_20) appended in place.
    """
    for window in windows:
        df[f"MA_{window}"] = df["Close"].rolling(window=window).mean()
    return df


def add_volume_signal(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Add a boolean column indicating whether today's volume is above its rolling average.

    Args:
        df: OHLCV DataFrame with a DatetimeIndex and a Volume column.
        window: Lookback period in days for the rolling volume average (default: 10).

    Returns:
        The input DataFrame with an additional boolean column
        Volume_Above_Avg appended in place.
    """
    df["Volume_Above_Avg"] = df["Volume"] > df["Volume"].rolling(window).mean()
    return df


def get_summary(df: pd.DataFrame) -> dict:
    """Summarise the most recent row of an enriched OHLCV DataFrame into a prompt-ready dict.

    Expects add_moving_averages(df, [10, 20]) and add_volume_signal(df)
    to have been called first.

    Args:
        df: OHLCV DataFrame enriched with MA_10, MA_20, and Volume_Above_Avg columns.

    Returns:
        A dict with the following keys, designed to be readable as
        direct input to the AI analyst prompt:
            current_price (float): Most recent closing price.
            ma_10 (float): 10-day simple moving average.
            ma_20 (float): 20-day simple moving average.
            volume_signal (str): "ABOVE AVERAGE" or "BELOW AVERAGE".
            price_vs_ma10 (str): "ABOVE" or "BELOW".
            price_vs_ma20 (str): "ABOVE" or "BELOW".
    """
    latest = df.iloc[-1]
    current_price = round(float(latest["Close"]), 2)
    ma_10 = round(float(latest["MA_10"]), 2)
    ma_20 = round(float(latest["MA_20"]), 2)

    return {
        "current_price": current_price,
        "ma_10": ma_10,
        "ma_20": ma_20,
        "volume_signal": "ABOVE AVERAGE" if latest["Volume_Above_Avg"] else "BELOW AVERAGE",
        "price_vs_ma10": "ABOVE" if current_price > ma_10 else "BELOW",
        "price_vs_ma20": "ABOVE" if current_price > ma_20 else "BELOW",
    }


if __name__ == "__main__":
    '''Example usage: Run this file directly to see the summary output for AAPL.'''
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.fetcher import get_stock_data

    df = get_stock_data("AAPL", 30)
    df = add_moving_averages(df, [10, 20])
    df = add_volume_signal(df)
    print(get_summary(df))
