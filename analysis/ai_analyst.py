"""AI signal generation for the StockPilot analysis pipeline."""


def build_prompt(ticker: str, summary: dict) -> str:
    """Construct a structured Anthropic API prompt for a single ticker.

    Args:
        ticker: The stock symbol being analysed (e.g. "AAPL").
        summary: Dict produced by indicators.get_summary — expected keys:
            current_price, ma_10, ma_20, volume_signal,
            price_vs_ma10, price_vs_ma20.

    Returns:
        A formatted prompt string ready to pass as the user message
        to the Anthropic API.
    """
    return f"""You are a quantitative trading analyst. Analyse the following technical data for {ticker} and produce a trading signal.

MARKET DATA FOR {ticker}
------------------------
Current price  : ${summary['current_price']:.2f}
10-day MA      : ${summary['ma_10']:.2f}  (price is {summary['price_vs_ma10']} this level)
20-day MA      : ${summary['ma_20']:.2f}  (price is {summary['price_vs_ma20']} this level)
Volume         : {summary['volume_signal']}

Based solely on this technical data, provide your assessment.

Respond using EXACTLY this format and no other text:

SIGNAL: <BULLISH|BEARISH|NEUTRAL>
CONFIDENCE: <High|Moderate|Low>
REASONING: <2-3 sentences explaining the key drivers behind your signal>
KEY_FACTORS:
- <factor 1>
- <factor 2>
- <factor 3>"""


if __name__ == "__main__":
    samples = [
        ("AAPL", {
            "current_price": 213.45,
            "ma_10": 208.30,
            "ma_20": 201.75,
            "volume_signal": "ABOVE AVERAGE",
            "price_vs_ma10": "ABOVE",
            "price_vs_ma20": "ABOVE",
        }),
        ("TSLA", {
            "current_price": 178.92,
            "ma_10": 185.60,
            "ma_20": 190.14,
            "volume_signal": "BELOW AVERAGE",
            "price_vs_ma10": "BELOW",
            "price_vs_ma20": "BELOW",
        }),
        ("NVDA", {
            "current_price": 131.10,
            "ma_10": 129.85,
            "ma_20": 124.40,
            "volume_signal": "ABOVE AVERAGE",
            "price_vs_ma10": "ABOVE",
            "price_vs_ma20": "ABOVE",
        }),
    ]

    for ticker, summary in samples:
        print("=" * 60)
        print(build_prompt(ticker, summary))
        print()
