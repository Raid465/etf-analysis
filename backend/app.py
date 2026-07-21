from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel
from typing import List, Optional
from backend import etf_data
import yfinance as yf
import os
import json
from datetime import datetime

app = FastAPI(title="ETF Analyzer")


@app.middleware("http")
async def add_security_headers(request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; img-src 'self' data:; connect-src 'self' https://query1.finance.yahoo.com"
    return response

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")
ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


def load_json_file(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


@app.get("/")
async def index():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })


@app.get("/api/etf/{symbol}")
async def analyze_etf(symbol: str):
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required.")
    try:
        info = etf_data.get_etf_info(symbol)
        holdings = etf_data.get_top_holdings(symbol)
        sectors = etf_data.get_sector_allocation(symbol)
        assets = etf_data.get_asset_allocation(symbol)
        metrics = etf_data.get_etf_metrics(symbol)
        prepost = etf_data.get_pre_post_market(symbol)
        desc = etf_data.get_fund_description(symbol)
        return {
            "info": info,
            "holdings": holdings,
            "sectors": sectors,
            "asset_allocation": assets,
            "metrics": metrics,
            "prepost": prepost,
            "description": desc,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data for '{symbol}': {str(e)}")


@app.get("/api/history/{symbol}")
async def get_price_history(symbol: str, period: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|2y|5y)$")):
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required.")
    try:
        data = etf_data.get_price_history(symbol, period)
        return {"symbol": symbol, "period": period, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history for '{symbol}': {str(e)}")


@app.get("/api/risk/{symbol}")
async def get_risk(symbol: str, period: str = Query("3y", pattern="^(1y|2y|3y|5y|10y)$")):
    symbol = symbol.strip().upper()
    try:
        return etf_data.get_risk_metrics(symbol, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dividends/{symbol}")
async def get_dividends(symbol: str):
    symbol = symbol.strip().upper()
    try:
        return {"symbol": symbol, "dividends": etf_data.get_dividend_history(symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/technical/{symbol}")
async def get_technical(symbol: str, period: str = Query("1y", pattern="^(6mo|1y|2y|5y)$")):
    symbol = symbol.strip().upper()
    try:
        return etf_data.get_technical_indicators(symbol, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/{symbol}")
async def get_news(symbol: str):
    symbol = symbol.strip().upper()
    try:
        return {"symbol": symbol, "news": etf_data.get_news(symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/movers")
async def get_movers(limit: int = Query(10, ge=3, le=20)):
    try:
        return etf_data.get_top_movers(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CompareRequest(BaseModel):
    symbol_a: str
    symbol_b: str


@app.post("/api/compare")
async def compare_etfs(req: CompareRequest):
    sym_a = req.symbol_a.strip().upper()
    sym_b = req.symbol_b.strip().upper()

    if not sym_a or not sym_b:
        raise HTTPException(status_code=400, detail="Both symbols are required.")
    if sym_a == sym_b:
        raise HTTPException(status_code=400, detail="Please provide two different ETF symbols.")

    try:
        info_a = etf_data.get_etf_info(sym_a)
        info_b = etf_data.get_etf_info(sym_b)
        metrics_a = etf_data.get_etf_metrics(sym_a)
        metrics_b = etf_data.get_etf_metrics(sym_b)
        holdings_a = etf_data.get_top_holdings(sym_a)
        holdings_b = etf_data.get_top_holdings(sym_b)
        overlap = etf_data.calculate_overlap(holdings_a, holdings_b)
        risk_a = etf_data.get_risk_metrics(sym_a)
        risk_b = etf_data.get_risk_metrics(sym_b)

        return {
            "etf_a": {"info": info_a, "metrics": metrics_a, "holdings": holdings_a, "risk": risk_a},
            "etf_b": {"info": info_b, "metrics": metrics_b, "holdings": holdings_b, "risk": risk_b},
            "overlap": overlap,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


class MultiCompareRequest(BaseModel):
    symbols: List[str]


@app.post("/api/multi-compare")
async def multi_compare(req: MultiCompareRequest):
    symbols = [s.strip().upper() for s in req.symbols if s.strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="At least 2 symbols required.")
    if len(symbols) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 symbols allowed.")

    try:
        perf = etf_data.get_performance_comparison(symbols)
        corr = etf_data.get_correlation(symbols)
        metrics = {}
        for sym in symbols:
            try:
                metrics[sym] = etf_data.get_etf_metrics(sym)
            except Exception:
                metrics[sym] = {}

        return {"performance": perf, "correlation": corr, "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CorrelationRequest(BaseModel):
    symbols: List[str]


@app.post("/api/correlation")
async def get_correlation(req: CorrelationRequest):
    symbols = [s.strip().upper() for s in req.symbols if s.strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="At least 2 symbols required.")
    try:
        return etf_data.get_correlation(symbols)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Watchlist endpoints
@app.get("/api/watchlist")
async def get_watchlist():
    return load_json_file(WATCHLIST_FILE, {"symbols": []})


@app.post("/api/watchlist/add")
async def add_to_watchlist(req: CompareRequest):
    data = load_json_file(WATCHLIST_FILE, {"symbols": []})
    sym = req.symbol_a.strip().upper()
    if sym and sym not in data["symbols"]:
        data["symbols"].append(sym)
        save_json_file(WATCHLIST_FILE, data)
    return data


@app.post("/api/watchlist/remove")
async def remove_from_watchlist(req: CompareRequest):
    data = load_json_file(WATCHLIST_FILE, {"symbols": []})
    sym = req.symbol_a.strip().upper()
    if sym in data["symbols"]:
        data["symbols"].remove(sym)
        save_json_file(WATCHLIST_FILE, data)
    return data


# Alerts endpoints
class AlertRequest(BaseModel):
    symbol: str
    target_price: float
    direction: str  # "above" or "below"


@app.get("/api/alerts")
async def get_alerts():
    return load_json_file(ALERTS_FILE, {"alerts": []})


@app.post("/api/alerts/add")
async def add_alert(req: AlertRequest):
    data = load_json_file(ALERTS_FILE, {"alerts": []})
    sym = req.symbol.strip().upper()
    alert = {
        "symbol": sym,
        "target_price": req.target_price,
        "direction": req.direction,
        "created": datetime.now().isoformat(),
    }
    data["alerts"].append(alert)
    save_json_file(ALERTS_FILE, data)
    return data


@app.post("/api/alerts/remove")
async def remove_alert(req: AlertRequest):
    data = load_json_file(ALERTS_FILE, {"alerts": []})
    sym = req.symbol.strip().upper()
    data["alerts"] = [
        a for a in data["alerts"]
        if not (a["symbol"] == sym and a["target_price"] == req.target_price)
    ]
    save_json_file(ALERTS_FILE, data)
    return data


@app.get("/api/alerts/check")
async def check_alerts():
    data = load_json_file(ALERTS_FILE, {"alerts": []})
    triggered = []
    remaining = []

    for alert in data["alerts"]:
        try:
            ticker = yf.Ticker(alert["symbol"])
            price = ticker.info.get("regularMarketPrice", 0)
            if alert["direction"] == "above" and price >= alert["target_price"]:
                triggered.append({**alert, "current_price": price})
            elif alert["direction"] == "below" and price <= alert["target_price"]:
                triggered.append({**alert, "current_price": price})
            else:
                remaining.append(alert)
        except Exception:
            remaining.append(alert)

    data["alerts"] = remaining
    save_json_file(ALERTS_FILE, data)
    return {"triggered": triggered, "remaining": remaining}


# Portfolio endpoints
class PortfolioHolding(BaseModel):
    symbol: str
    shares: float
    avgPrice: Optional[float] = 0


class PortfolioRequest(BaseModel):
    name: str
    holdings: List[PortfolioHolding]


@app.get("/api/portfolio")
async def get_portfolio():
    return load_json_file(PORTFOLIO_FILE, {"portfolios": []})


@app.post("/api/portfolio/save")
async def save_portfolio(req: PortfolioRequest):
    data = load_json_file(PORTFOLIO_FILE, {"portfolios": []})
    holdings_data = []
    total_value = 0
    total_cost = 0

    for h in req.holdings:
        try:
            ticker = yf.Ticker(h.symbol)
            price = ticker.info.get("regularMarketPrice", 0)
            value = price * h.shares
            cost = (h.avgPrice or 0) * h.shares
            total_value += value
            total_cost += cost
            holdings_data.append({
                "symbol": h.symbol.upper(),
                "shares": h.shares,
                "avgPrice": h.avgPrice or 0,
                "price": round(price, 2),
                "value": round(value, 2),
                "cost": round(cost, 2),
                "pl": round(value - cost, 2),
            })
        except Exception:
            continue

    for hd in holdings_data:
        hd["weight"] = round(hd["value"] / total_value * 100, 2) if total_value > 0 else 0

    portfolio = {
        "name": req.name,
        "holdings": holdings_data,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pl": round(total_value - total_cost, 2),
        "created": datetime.now().isoformat(),
    }

    data["portfolios"].append(portfolio)
    save_json_file(PORTFOLIO_FILE, data)
    return portfolio


# PDF Export data endpoint
@app.get("/api/report/{symbol}")
async def get_report_data(symbol: str):
    symbol = symbol.strip().upper()
    try:
        info = etf_data.get_etf_info(symbol)
        metrics = etf_data.get_etf_metrics(symbol)
        holdings = etf_data.get_top_holdings(symbol)
        sectors = etf_data.get_sector_allocation(symbol)
        assets = etf_data.get_asset_allocation(symbol)
        risk = etf_data.get_risk_metrics(symbol)
        dividends = etf_data.get_dividend_history(symbol)[:12]
        desc = etf_data.get_fund_description(symbol)

        return {
            "info": info,
            "metrics": metrics,
            "holdings": holdings,
            "sectors": sectors,
            "asset_allocation": assets,
            "risk": risk,
            "dividends": dividends,
            "description": desc,
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Saudi ETF Endpoints ===
from backend import saudi_etf


@app.get("/api/saudi/list")
async def get_saudi_etf_list():
    return {"etfs": saudi_etf.get_saudi_etf_list()}


@app.get("/api/saudi/{symbol}")
async def analyze_saudi_etf(symbol: str):
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required.")
    try:
        info = saudi_etf.get_saudi_etf_info(symbol)
        holdings = saudi_etf.get_saudi_etf_holdings(symbol)
        risk = saudi_etf.get_saudi_etf_risk(symbol)
        return {
            "info": info,
            "holdings": holdings,
            "risk": risk,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/saudi/history/{symbol}")
async def get_saudi_etf_history(symbol: str, period: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|2y|5y)$")):
    symbol = symbol.strip().upper()
    try:
        data = saudi_etf.get_saudi_etf_history(symbol, period)
        return {"symbol": symbol, "period": period, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/saudi/holdings/{symbol}")
async def get_saudi_etf_holdings(symbol: str):
    """Get holdings for a Saudi ETF or REIT."""
    symbol = symbol.strip().upper()
    try:
        holdings = saudi_etf.get_saudi_etf_holdings(symbol)
        return {"symbol": symbol, "holdings": holdings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SaudiCompareRequest(BaseModel):
    symbol_a: str
    symbol_b: str


@app.post("/api/saudi/compare")
async def compare_saudi_etfs(req: SaudiCompareRequest):
    sym_a = req.symbol_a.strip().upper()
    sym_b = req.symbol_b.strip().upper()
    if not sym_a or not sym_b:
        raise HTTPException(status_code=400, detail="Both symbols are required.")
    if sym_a == sym_b:
        raise HTTPException(status_code=400, detail="Please provide two different symbols.")
    try:
        return saudi_etf.compare_saudi_etfs(sym_a, sym_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mutual Funds (صناديق الاستثمار العامة)
MUTUAL_FUNDS_FILE = os.path.join(os.path.dirname(__file__), "mutual_funds.json")

_MUTUAL_FUNDS_CACHE = None

def load_mutual_funds():
    """Load mutual funds from JSON file (cached in memory)."""
    global _MUTUAL_FUNDS_CACHE
    if _MUTUAL_FUNDS_CACHE is None:
        if os.path.exists(MUTUAL_FUNDS_FILE):
            with open(MUTUAL_FUNDS_FILE, "r", encoding="utf-8") as f:
                _MUTUAL_FUNDS_CACHE = json.load(f)
        else:
            _MUTUAL_FUNDS_CACHE = []
    return _MUTUAL_FUNDS_CACHE


@app.get("/api/mutual-funds")
async def get_mutual_funds(
    search: Optional[str] = Query(None, description="Search by name"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    objective: Optional[str] = Query(None, description="Filter by objective"),
    sharia: Optional[str] = Query(None, description="Filter by Sharia compliance"),
    manager: Optional[str] = Query(None, description="Filter by fund manager"),
    sort_by: Optional[str] = Query("nav", description="Sort by: nav, ytd, name"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200)
):
    """Get list of all mutual funds with filtering and pagination."""
    funds = load_mutual_funds()

    # Apply filters
    if search:
        search_lower = search.lower()
        funds = [f for f in funds if search_lower in f.get("name", "").lower()
                 or search_lower in f.get("symbol", "").lower()]

    if currency:
        funds = [f for f in funds if f.get("currency") == currency]

    if objective:
        funds = [f for f in funds if f.get("objective") == objective]

    if sharia:
        funds = [f for f in funds if f.get("shariaCompliant") == sharia]

    if manager:
        funds = [f for f in funds if f.get("fundManager") == manager]

    # Sort
    def sort_key(fund):
        if sort_by == "nav":
            try:
                return float(fund.get("nav", "0").replace(",", ""))
            except:
                return 0
        elif sort_by == "ytd":
            try:
                return float(fund.get("ytdChange", "0"))
            except:
                return 0
        elif sort_by == "name":
            return fund.get("name", "")
        return 0

    funds.sort(key=sort_key, reverse=(sort_order == "desc"))

    # Pagination
    total = len(funds)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_funds = funds[start:end]

    # Get unique values for filters
    currencies = list(set(f.get("currency", "") for f in funds))
    objectives = list(set(f.get("objective", "") for f in funds))
    sharia_options = list(set(f.get("shariaCompliant", "") for f in funds))
    managers = list(set(f.get("fundManager", "") for f in funds))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "funds": paginated_funds,
        "filters": {
            "currencies": sorted(currencies),
            "objectives": sorted(objectives),
            "sharia_options": sorted(sharia_options),
            "managers": sorted(managers)
        }
    }


@app.get("/api/mutual-funds/stats")
async def get_mutual_funds_stats():
    """Get statistics about mutual funds."""
    funds = load_mutual_funds()

    total_funds = len(funds)
    total_nav = 0
    for f in funds:
        try:
            nav_str = f.get("nav", "0").replace(",", "")
            total_nav += float(nav_str)
        except:
            pass

    # Count by currency
    currencies = {}
    for f in funds:
        cur = f.get("currency", "غير محدد")
        currencies[cur] = currencies.get(cur, 0) + 1

    # Count by objective
    objectives = {}
    for f in funds:
        obj = f.get("objective", "غير محدد")
        objectives[obj] = objectives.get(obj, 0) + 1

    # Top funds by NAV
    sorted_funds = sorted(funds, key=lambda x: float(x.get("nav", "0").replace(",", "")), reverse=True)
    top_funds = sorted_funds[:10]

    return {
        "total_funds": total_funds,
        "total_nav": total_nav,
        "currencies": currencies,
        "objectives": objectives,
        "top_funds": top_funds
    }


@app.get("/api/mutual-funds/{symbol}")
async def get_mutual_fund_detail(symbol: str):
    """Get details of a specific mutual fund."""
    funds = load_mutual_funds()
    fund = next((f for f in funds if f.get("symbol") == symbol), None)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    return fund


FUND_HOLDINGS_FILE = os.path.join(os.path.dirname(__file__), "fund_holdings.json")

_FUND_HOLDINGS_CACHE = None

def load_fund_holdings():
    global _FUND_HOLDINGS_CACHE
    if _FUND_HOLDINGS_CACHE is None:
        if os.path.exists(FUND_HOLDINGS_FILE):
            with open(FUND_HOLDINGS_FILE, "r", encoding="utf-8") as f:
                _FUND_HOLDINGS_CACHE = json.load(f)
        else:
            _FUND_HOLDINGS_CACHE = {}
    return _FUND_HOLDINGS_CACHE


@app.get("/api/mutual-funds/{symbol}/holdings")
async def get_mutual_fund_holdings(symbol: str):
    """Get holdings for a specific mutual fund."""
    all_holdings = load_fund_holdings()
    holdings = all_holdings.get(symbol, [])
    return {"symbol": symbol, "holdings": holdings}


FUND_DIVIDENDS_FILE = os.path.join(os.path.dirname(__file__), "fund_dividends.json")

_FUND_DIVIDENDS_CACHE = None

def load_fund_dividends():
    global _FUND_DIVIDENDS_CACHE
    if _FUND_DIVIDENDS_CACHE is None:
        if os.path.exists(FUND_DIVIDENDS_FILE):
            with open(FUND_DIVIDENDS_FILE, "r", encoding="utf-8") as f:
                _FUND_DIVIDENDS_CACHE = json.load(f)
        else:
            _FUND_DIVIDENDS_CACHE = {}
    return _FUND_DIVIDENDS_CACHE


@app.get("/api/saudi/dividends/{symbol}")
async def get_saudi_dividends(symbol: str):
    """Get dividend distributions for a Saudi ETF, REIT, or mutual fund."""
    all_divs = load_fund_dividends()
    div_data = all_divs.get(symbol, None)
    if div_data is None:
        return {"symbol": symbol, "annualYield": 0, "dividendsPerYear": 0, "distributions": []}
    return {"symbol": symbol, **div_data}
