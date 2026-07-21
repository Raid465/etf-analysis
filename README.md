# ETF Analyzer

A comprehensive ETF and mutual fund analysis tool with Arabic-language interface, supporting US ETFs, Saudi ETFs/REITs, and Saudi mutual funds.

## Features

- **ETF Analysis** — info, holdings, sectors, dividends, risk metrics, price history
- **Compare** — side-by-side comparison of two funds with overlap ratio
- **Multi-Compare** — compare 3+ funds at once
- **Market Movers** — top gainers and losers
- **Saudi ETFs/REITs** — 13 ETFs + 13 REITs from Tadawul
- **Mutual Funds** — 353 Saudi mutual funds with search, filter, sort, pagination
- **Dividends** — REIT and mutual fund distribution data with annual yield
- **Watchlist / Alerts / Portfolio** — personal tracking tools

## Tech Stack

- **Backend:** Python FastAPI + Yahoo Finance API
- **Frontend:** Single-page HTML/CSS/JS + Chart.js
- **Cache:** SQLite with 24-hour TTL
- **Database:** JSON files for fund data, SQLite for API cache

## Quick Start

```
pip install -r backend\requirements.txt
python run.py
```

Open http://localhost:8000

## Project Structure

```
├── backend/
│   ├── app.py              # FastAPI server (routes, middleware)
│   ├── etf_data.py         # US ETF data & Yahoo Finance integration
│   ├── saudi_etf.py        # Saudi ETF/REIT data & holdings
│   ├── cache.py            # SQLite caching layer
│   ├── mutual_funds.json   # 353 Saudi mutual funds
│   ├── fund_holdings.json  # Mutual fund holdings data
│   ├── fund_dividends.json # Dividend distribution data
│   └── requirements.txt
├── frontend/
│   └── index.html          # Single-page Arabic UI
├── run.py                  # Entry point
├── audit_test.py           # QA audit tests
└── README.md
```
