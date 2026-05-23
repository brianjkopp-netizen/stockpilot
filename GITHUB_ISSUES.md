# StockPilot -- GitHub Issues
## Milestone 1 & 2 | Ready to Paste
**Project timeline:** May 27 -- August 14, 2026 | 12 weeks | Week 1 is May 27-29 (3 days)

Copy each block below directly into a new GitHub Issue.
Set the Label, Milestone, and Assignee as noted before saving.

---

## MILESTONE 1 -- Data Foundation | May 27 -- Jun 12

---

### Issue M1-01

**Title:** Set up project repository structure and development environment

**Label:** `chore` `milestone-1` `good-first-issue`
**Milestone:** Milestone 1 -- Data Foundation
**Assignee:** [son]

---

**User Story**
As a developer, I want a clean, organized project structure so that every module has a clear home and the repo is ready for collaboration from day one.

**Acceptance Criteria**
- [ ] GitHub repo created and set to public
- [ ] Folder structure matches the spec below
- [ ] `requirements.txt` includes initial dependencies (`yfinance`, `python-dotenv`, `anthropic`)
- [ ] `.gitignore` excludes `.env`, `__pycache__`, `.venv`, `*.pyc`
- [ ] `.env.example` file committed with placeholder keys (no real keys ever committed)
- [ ] `README.md` (from project brief) committed to root
- [ ] `CLAUDE.md` committed to root with project context filled in
- [ ] Virtual environment created locally (not committed)

**Folder Structure**
```
stockpilot/
├── data/
│   └── fetcher.py
├── analysis/
│   ├── indicators.py
│   └── ai_analyst.py
├── trading/
│   └── alpaca_client.py
├── portfolio/
│   └── tracker.py
├── app/
│   └── main.py
├── .env.example
├── .gitignore
├── CLAUDE.md
├── requirements.txt
└── README.md
```

**Technical Notes**
- Use `python -m venv .venv` to create the virtual environment
- Use Claude Code to generate the `.gitignore` -- prompt: *"Generate a .gitignore for a Python project using yfinance, dotenv, and the Anthropic SDK"*
- Do not push any file containing a real API key

---

### Issue M1-02

**Title:** Build stock data fetcher module

**Label:** `feature` `milestone-1` `good-first-issue`
**Milestone:** Milestone 1 -- Data Foundation
**Assignee:** [son]

---

**User Story**
As a user, I want the app to fetch historical price and volume data for any stock ticker so that the analysis pipeline has real market data to work with.

**Acceptance Criteria**
- [ ] `data/fetcher.py` contains a function `get_stock_data(ticker: str, days: int) -> pd.DataFrame`
- [ ] Function returns a pandas DataFrame with columns: Date, Open, High, Low, Close, Volume
- [ ] Function raises a descriptive `ValueError` if the ticker is invalid or returns no data
- [ ] Function raises a descriptive `ConnectionError` if the network request fails
- [ ] Docstring written in Google style
- [ ] Manual test passes: running `fetcher.py` directly prints last 30 days of AAPL data to terminal

**Technical Notes**
- Use the `yfinance` library (`yf.Ticker(ticker).history(period=f"{days}d")`)
- Reference: https://pypi.org/project/yfinance/
- Claude Code prompt to start: *"Write a function called get_stock_data(ticker: str, days: int) -> pd.DataFrame using yfinance. Return OHLCV data. Handle invalid tickers and network errors with descriptive exceptions. Add a Google-style docstring."*
- After Claude Code writes it, run it yourself and verify the output before committing

---

### Issue M1-03

**Title:** Build technical indicators module

**Label:** `feature` `milestone-1`
**Milestone:** Milestone 1 -- Data Foundation
**Assignee:** [son]

---

**User Story**
As a user, I want the app to calculate basic technical indicators from raw price data so that the AI signal engine has meaningful inputs beyond raw price.

**Acceptance Criteria**
- [ ] `analysis/indicators.py` contains the following functions:
  - `add_moving_averages(df: pd.DataFrame, windows: list[int]) -> pd.DataFrame` -- adds MA columns (e.g. MA_10, MA_20)
  - `add_volume_signal(df: pd.DataFrame) -> pd.DataFrame` -- adds a column indicating whether today's volume is above the 10-day average
  - `get_summary(df: pd.DataFrame) -> dict` -- returns a dict with current price, MA_10, MA_20, volume signal, and price vs. MA relationship
- [ ] All functions include Google-style docstrings and type hints
- [ ] Manual test passes: running indicators on AAPL data prints a clean summary dict to terminal

**Technical Notes**
- Moving averages: `df['Close'].rolling(window=n).mean()`
- Volume signal: compare today's volume to `df['Volume'].rolling(10).mean()`
- The `get_summary()` dict will be passed directly to the AI analyst in Milestone 2 -- design it to be readable as a prompt input
- Use Claude Code's refactor pattern: write a rough version first, then ask Claude Code to clean it up and add type hints

---

### Issue M1-04

**Title:** Build main entry point and wire the pipeline

**Label:** `feature` `milestone-1`
**Milestone:** Milestone 1 -- Data Foundation
**Assignee:** [son]

---

**User Story**
As a user, I want to run a single command with a ticker symbol and get a clean terminal output of that stock's data and indicators so that I can verify the full data pipeline works end to end.

**Acceptance Criteria**
- [ ] `app/main.py` accepts a `--ticker` argument and optional `--days` argument (default: 30)
- [ ] Running `python app/main.py --ticker AAPL` prints a formatted summary to terminal
- [ ] Output includes: ticker, date range, current price, MA_10, MA_20, volume signal
- [ ] Error messages are user-friendly (not raw Python tracebacks)
- [ ] Works for at least 3 different valid tickers tested manually

**Technical Notes**
- Use Python's `argparse` library for CLI arguments
- Claude Code prompt: *"Write a main.py entry point using argparse that accepts --ticker and --days arguments, calls get_stock_data() and get_summary(), and prints a clean formatted output to the terminal. Include error handling that catches ValueError and ConnectionError and prints friendly messages."*
- Test with: `AAPL`, `TSLA`, `NVDA`, and one invalid ticker like `ZZZZZ`

---

### Issue M1-05

**Title:** Milestone 1 review -- code quality and documentation pass

**Label:** `chore` `milestone-1`
**Milestone:** Milestone 1 -- Data Foundation
**Assignee:** [son]

---

**User Story**
As a product manager, I want to review all Milestone 1 code before moving to AI integration so that we're building on a clean foundation and the repo tells a coherent story.

**Acceptance Criteria**
- [ ] All functions in `fetcher.py` and `indicators.py` have docstrings
- [ ] No hardcoded values (tickers, day counts) anywhere except `main.py` defaults
- [ ] `README.md` Phase 1 checklist updated to reflect completed items
- [ ] All Milestone 1 issues closed in GitHub
- [ ] Code reviewed by Brian (PR opened, comments addressed, PR merged)

**Technical Notes**
- Use Claude Code to do a final review pass: *"Review all files in this project for missing docstrings, hardcoded values, and inconsistent naming. List every issue you find."*
- This issue is not closed until Brian approves the PR

---

## MILESTONE 2 -- AI Signal Engine | Jun 13 -- Jul 3

---

### Issue M2-01

**Title:** Build AI analyst module -- prompt construction

**Label:** `feature` `milestone-2`
**Milestone:** Milestone 2 -- AI Signal Engine
**Assignee:** [son]

---

**User Story**
As a user, I want the app to send structured stock data to an AI model so that I get a signal and plain-language reasoning rather than raw numbers.

**Acceptance Criteria**
- [ ] `analysis/ai_analyst.py` contains a function `build_prompt(ticker: str, summary: dict) -> str`
- [ ] Prompt is structured, readable, and includes: ticker, current price, MA_10, MA_20, volume signal, and explicit instructions for the output format
- [ ] Prompt instructs the model to respond with: Signal (BULLISH / BEARISH / NEUTRAL), Confidence (High / Moderate / Low), and 2-3 sentence Reasoning
- [ ] Prompt is tested manually by printing it to terminal before any API call is made
- [ ] Google-style docstring included

**Technical Notes**
- Build the prompt as a formatted string using the `summary` dict from `indicators.get_summary()`
- The prompt should include explicit output format instructions -- this is what makes the API response parseable
- Claude Code prompt: *"Write a function called build_prompt(ticker: str, summary: dict) -> str that constructs a structured prompt for the Anthropic API. The prompt should include all values from the summary dict, ask for a BULLISH/BEARISH/NEUTRAL signal, a confidence level, and 2-3 sentences of reasoning. Format the output section explicitly so it can be parsed."*
- Print the prompt for 3 different tickers before moving to M2-02

---

### Issue M2-02

**Title:** Build AI analyst module -- Anthropic API integration

**Label:** `feature` `milestone-2`
**Milestone:** Milestone 2 -- AI Signal Engine
**Assignee:** [son]

---

**User Story**
As a user, I want the app to call the Anthropic API with the structured prompt and return a parsed signal object so that downstream features can act on the AI's recommendation.

**Acceptance Criteria**
- [ ] `analysis/ai_analyst.py` contains a function `get_signal(ticker: str, summary: dict) -> dict`
- [ ] Function calls the Anthropic API using the `anthropic` Python SDK
- [ ] API key loaded from environment variable (`ANTHROPIC_API_KEY`), never hardcoded
- [ ] Function returns a dict with keys: `ticker`, `signal`, `confidence`, `reasoning`
- [ ] Function handles API errors with descriptive exceptions
- [ ] Manual test passes: `get_signal("AAPL", summary)` returns a properly structured dict

**Technical Notes**
- Use `anthropic` SDK: `client = anthropic.Anthropic()` then `client.messages.create(...)`
- Model: `claude-sonnet-4-20250514`
- Parse the response from `response.content[0].text`
- Claude Code prompt for the parsing logic: *"Write a function that takes the raw text response from the Anthropic API and parses it into a dict with keys: signal, confidence, reasoning. The response will follow this format: [paste your prompt's output format]. Handle cases where parsing fails gracefully."*
- Test with at least 5 different tickers and inspect the raw response before relying on the parser

---

### Issue M2-03

**Title:** Wire AI signal into main entry point

**Label:** `feature` `milestone-2`
**Milestone:** Milestone 2 -- AI Signal Engine
**Assignee:** [son]

---

**User Story**
As a user, I want to run a single command and see both the technical indicator summary and the AI signal so that I have a complete picture of the stock in one output.

**Acceptance Criteria**
- [ ] `app/main.py` updated to call `get_signal()` after `get_summary()`
- [ ] Terminal output displays: ticker, price, indicators, signal, confidence, and reasoning
- [ ] Output is clearly formatted and readable (use separator lines or labels)
- [ ] Total runtime displayed at the end (so we can see API latency)
- [ ] Works end-to-end for at least 3 tickers without errors

**Sample Output**
```
============================================================
StockPilot -- AI Signal Analysis
============================================================
Ticker:         AAPL
Date Range:     2026-04-22 to 2026-05-22
Current Price:  $189.42
MA (10-day):    $187.15
MA (20-day):    $183.90
Volume Signal:  ABOVE AVERAGE

--- AI Signal ---
Signal:         BULLISH
Confidence:     Moderate
Reasoning:      Price is trading above both moving averages with
                above-average volume on up days. No major reversal
                signals in the near-term window. Watch for resistance
                near the 52-week high.

Runtime: 2.3s
============================================================
```

**Technical Notes**
- Use Python's `time` module to measure runtime: `start = time.time()` before the pipeline, `elapsed = time.time() - start` at the end
- Claude Code prompt: *"Update main.py to call get_signal() after get_summary() and display a formatted terminal output that includes both the indicator summary and the AI signal. Add runtime tracking."*

---

### Issue M2-04

**Title:** Add signal history logging

**Label:** `feature` `milestone-2`
**Milestone:** Milestone 2 -- AI Signal Engine
**Assignee:** [son]

---

**User Story**
As a user, I want every signal generated to be saved to a local log file so that I can review past signals and eventually compare them to actual price movement.

**Acceptance Criteria**
- [ ] Every call to `get_signal()` appends a record to `signals_log.json`
- [ ] Each record includes: timestamp, ticker, signal, confidence, reasoning, price at time of signal
- [ ] Log file is excluded from `.gitignore` (it's local data, not code)
- [ ] A helper function `load_signal_history(ticker: str) -> list` returns all past signals for a given ticker
- [ ] Manual test: run the app 3 times for the same ticker, verify 3 records appear in the log

**Technical Notes**
- Use Python's `json` module -- append to a list stored in the file
- Timestamp: `datetime.now().isoformat()`
- Claude Code prompt: *"Write a function called log_signal(signal_dict: dict, price: float) -> None that appends a signal record with a timestamp to a local signals_log.json file. Also write load_signal_history(ticker: str) -> list that returns all records for a given ticker. Handle the case where the file doesn't exist yet."*
- Add `signals_log.json` to `.gitignore` -- this file will eventually contain real paper trading history

---

### Issue M2-05

**Title:** Milestone 2 review -- AI integration quality pass

**Label:** `chore` `milestone-2`
**Milestone:** Milestone 2 -- AI Signal Engine
**Assignee:** [son]

---

**User Story**
As a product manager, I want to review all Milestone 2 code and run the full pipeline myself before we move to paper trading so that I'm confident the signal engine is reliable enough to drive buy decisions.

**Acceptance Criteria**
- [ ] Brian runs the full pipeline for 5 tickers and reviews output quality
- [ ] All API keys confirmed to be in `.env` only -- none in code
- [ ] Signal parsing handles edge cases (API timeout, malformed response)
- [ ] `README.md` Phase 2 checklist updated
- [ ] All Milestone 2 issues closed
- [ ] PR opened, reviewed by Brian, and merged to main

**Technical Notes**
- Brian's review checklist:
  - Does the signal reasoning make logical sense given the indicator data?
  - Is the output format consistent across different tickers?
  - Does the app fail gracefully when the API is slow or unavailable?
  - Is the log file growing correctly?
- This gate matters -- Milestone 3 connects real (paper) money. The signal engine needs to be trustworthy before we give it a buy button.
