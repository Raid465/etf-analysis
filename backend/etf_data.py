import yfinance as yf
import requests
import re
import json
import math
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from backend import cache

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def get_etf_info(ticker_symbol: str) -> dict:
    cache_key = f"info:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    if not info or info.get("quoteType") not in ("ETF", "MUTUALFUND"):
        fund_name = info.get("longName") or info.get("shortName") or ""
        if not fund_name:
            raise ValueError(f"ETF '{ticker_symbol}' not found or invalid ticker.")

    result = {
        "symbol": ticker_symbol.upper(),
        "name": info.get("longName") or info.get("shortName") or ticker_symbol.upper(),
        "expense_ratio": info.get("annualReportExpenseRatio"),
        "aum": info.get("totalAssets"),
        "inception_date": info.get("fundInceptionDate"),
        "category": info.get("category", ""),
        "provider": info.get("fundFamily", ""),
    }
    cache.set(cache_key, result)
    return result


def _fetch_holdings_from_stockanalysis(symbol: str) -> list:
    url = f'https://stockanalysis.com/etf/{symbol.lower()}/holdings/'
    headers = {'User-Agent': USER_AGENT}

    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, 'html.parser')

    # Extract from embedded JavaScript data (SvelteKit)
    for s in soup.find_all('script'):
        if not s.string or 'holdings:[' not in s.string or len(s.string) < 1000:
            continue
        idx = s.string.find('holdings:[')
        start = idx + len('holdings:')
        bracket_count = 0
        i = start
        while i < len(s.string):
            if s.string[i] == '[':
                bracket_count += 1
            elif s.string[i] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            i += 1

        json_str = s.string[start:i+1]
        json_str = re.sub(r'(\{|,)(\w+):', r'\1"\2":', json_str)

        try:
            data = json.loads(json_str)
            holdings = []
            for h in data:
                sym = h.get('s', '').replace('$', '')
                name = h.get('n', '')
                weight_str = str(h.get('as', '0%')).replace('%', '')
                try:
                    weight = float(weight_str)
                except (ValueError, TypeError):
                    weight = 0.0
                holdings.append({
                    'symbol': sym,
                    'name': name,
                    'weight': weight,
                })
            return holdings
        except json.JSONDecodeError:
            continue

    # Fallback: parse HTML table
    tables = soup.find_all('table')
    if tables:
        holdings = []
        for row in tables[0].find_all('tr')[1:]:
            cells = row.find_all('td')
            if len(cells) >= 4:
                sym = cells[1].get_text(strip=True)
                name = cells[2].get_text(strip=True)
                weight_str = cells[3].get_text(strip=True).replace('%', '')
                try:
                    weight = float(weight_str)
                except (ValueError, TypeError):
                    weight = 0.0
                holdings.append({'symbol': sym, 'name': name, 'weight': weight})
        return holdings

    return []


def get_top_holdings(ticker_symbol: str) -> list:
    cache_key = f"holdings:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Try stockanalysis.com first (more holdings)
    holdings = _fetch_holdings_from_stockanalysis(ticker_symbol)

    # Fallback to yfinance if stockanalysis fails
    if not holdings:
        ticker = yf.Ticker(ticker_symbol)
        try:
            fd = ticker.funds_data
            if fd and fd.top_holdings is not None:
                df = fd.top_holdings
                for idx, row in df.iterrows():
                    symbol_val = str(idx) if idx else ""
                    name_val = ""
                    pct_val = 0.0
                    for col in df.columns:
                        col_lower = str(col).lower()
                        if "name" in col_lower and "percent" not in col_lower:
                            name_val = str(row[col])
                        elif "weight" in col_lower or "percent" in col_lower or "%" in col_lower:
                            try:
                                pct_val = float(row[col])
                                if pct_val > 1:
                                    pct_val = pct_val / 100.0
                            except (ValueError, TypeError):
                                pct_val = 0.0
                    if not symbol_val and name_val:
                        symbol_val = name_val
                    holdings.append({
                        "symbol": symbol_val,
                        "name": name_val,
                        "weight": round(pct_val * 100, 2),
                    })
        except Exception:
            pass

    cache.set(cache_key, holdings)
    return holdings


def get_sector_allocation(ticker_symbol: str) -> dict:
    cache_key = f"sectors:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    sectors = {}

    try:
        fd = ticker.funds_data
        if fd and fd.sector_weightings is not None:
            for key, val in fd.sector_weightings.items():
                if val is not None and val > 0:
                    sectors[str(key)] = round(float(val) * 100, 2)
    except Exception:
        pass

    cache.set(cache_key, sectors)
    return sectors


def get_asset_allocation(ticker_symbol: str) -> dict:
    cache_key = f"assets:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    assets = {}

    try:
        fd = ticker.funds_data
        if fd and fd.asset_classes is not None:
            for key, val in fd.asset_classes.items():
                if val is not None and val > 0:
                    assets[str(key)] = round(float(val) * 100, 2)
    except Exception:
        pass

    cache.set(cache_key, assets)
    return assets


def _normalize_name(name: str) -> str:
    """Normalize company name for matching."""
    name = name.lower().strip()

    # Remove swap/derivative indicators (do this before suffix removal)
    swap_patterns = [
        r'\btrs\b', r'\bswap\b', r'\bdr\b', r'\badr\b',
        r'\bnm\b', r'\bgs\b', r'\bgold\b', r'\bl\b',
    ]
    for pat in swap_patterns:
        name = re.sub(pat, ' ', name)

    # Remove dates like 09/08/2026 or 050427
    name = re.sub(r'\d{2}[/.-]\d{2}[/.-]\d{2,4}', '', name)
    name = re.sub(r'\b\d{6}\b', '', name)

    # Remove common suffixes anywhere in the string
    suffixes = [
        ' corporation', ' company', ' limited', ' holdings', ' holding',
        ' inc', ' ltd', ' corp', ' co', ' plc', ' group',
    ]
    for suffix in suffixes:
        name = name.replace(suffix, ' ')

    # Remove special characters
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _extract_core_name(name: str) -> str:
    """Extract the core company name for matching."""
    name = _normalize_name(name)
    # Remove common prefixes
    for prefix in ['the ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def calculate_overlap(holdings_a: list, holdings_b: list) -> dict:
    # Build unified weight map by normalized name for each fund
    def build_weight_map(holdings):
        """Build a map of normalized_name -> total_weight for all holdings."""
        weight_map = {}
        name_display = {}  # For display purposes
        
        for h in holdings:
            name = h.get("name", "")
            sym = h.get("symbol", "").upper()
            weight = h.get("weight", 0.0)
            norm = _extract_core_name(name)
            
            if not norm:
                norm = sym
            if not norm:
                continue
            
            # Sum weights for same company (e.g., swap + direct stock)
            if norm in weight_map:
                weight_map[norm] += weight
            else:
                weight_map[norm] = weight
                name_display[norm] = {
                    "symbol": sym,
                    "name": name,
                }
        
        return weight_map, name_display
    
    map_a, display_a = build_weight_map(holdings_a)
    map_b, display_b = build_weight_map(holdings_b)
    
    # Find all companies in either fund
    all_companies = set(map_a.keys()) | set(map_b.keys())
    
    overlap_total = 0.0
    shared = []
    
    for company in all_companies:
        w_a = map_a.get(company, 0.0)
        w_b = map_b.get(company, 0.0)
        contribution = min(w_a, w_b)
        overlap_total += contribution
        
        # Only add to shared if both funds have this company
        if w_a > 0 and w_b > 0:
            # Get display info
            info = display_a.get(company, display_b.get(company, {}))
            shared.append({
                "symbol": info.get("symbol", ""),
                "name": info.get("name", ""),
                "weight_a": round(w_a, 2),
                "weight_b": round(w_b, 2),
                "contribution": round(contribution, 2),
            })
    
    shared.sort(key=lambda x: x["contribution"], reverse=True)
    
    overlap_pct = round(overlap_total, 2)
    
    if overlap_pct < 20:
        interpretation = "تنويع جيد — تداخل منخفض بين الصندوقين يقلل التكرار."
    elif overlap_pct <= 50:
        interpretation = "تداخل متوسط — هناك تشابه ملحوظ في بعض المراكز."
    else:
        interpretation = "تداخل كبير — تكرار غير مفيد، قد تفكر بدمج الصندوقين."
    
    return {
        "overlap_percentage": overlap_pct,
        "shared_holdings": shared,
        "interpretation": interpretation,
        "holdings_count_a": len(holdings_a),
        "holdings_count_b": len(holdings_b),
        "shared_count": len(shared),
    }


def get_etf_metrics(ticker_symbol: str) -> dict:
    """Get extended ETF metrics including P/E, P/B, volume, returns, etc."""
    cache_key = f"metrics:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    if not info or not info.get("quoteType"):
        raise ValueError(f"ETF '{ticker_symbol}' not found.")

    # Price data
    current_price = info.get("regularMarketPrice") or info.get("previousClose")
    previous_close = info.get("previousClose")
    day_change = info.get("regularMarketChange")
    day_change_pct = info.get("regularMarketChangePercent")

    # Volume
    volume = info.get("regularMarketVolume")
    avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")

    # Valuation ratios
    trailing_pe = info.get("trailingPE")
    price_to_book = info.get("priceToBook")

    # Returns
    ytd_return = info.get("ytdReturn")
    three_year_return = info.get("threeYearAverageReturn")
    five_year_return = info.get("fiveYearAverageReturn")

    # 52-week range
    week52_high = info.get("fiftyTwoWeekHigh")
    week52_low = info.get("fiftyTwoWeekLow")

    # Moving averages
    ma50 = info.get("fiftyDayAverage")
    ma200 = info.get("twoHundredDayAverage")

    # Beta
    beta = info.get("beta3Year")

    # Expense ratio
    expense_ratio = info.get("netExpenseRatio") or info.get("annualReportExpenseRatio")

    # Dividend yield
    yield_val = info.get("yield")

    # NAV
    nav = info.get("navPrice")

    result = {
        "current_price": current_price,
        "previous_close": previous_close,
        "day_change": round(day_change, 2) if day_change else None,
        "day_change_pct": round(day_change_pct, 2) if day_change_pct else None,
        "volume": volume,
        "avg_volume": avg_volume,
        "trailing_pe": round(trailing_pe, 2) if trailing_pe else None,
        "price_to_book": round(price_to_book, 2) if price_to_book else None,
        "ytd_return": round(ytd_return, 2) if ytd_return else None,
        "three_year_return": round(three_year_return * 100, 2) if three_year_return else None,
        "five_year_return": round(five_year_return * 100, 2) if five_year_return else None,
        "week52_high": round(week52_high, 2) if week52_high else None,
        "week52_low": round(week52_low, 2) if week52_low else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "beta": round(beta, 2) if beta else None,
        "expense_ratio": round(expense_ratio, 2) if expense_ratio else None,
        "dividend_yield": round(yield_val * 100, 2) if yield_val else None,
        "nav": round(nav, 2) if nav else None,
    }

    cache.set(cache_key, result)
    return result


def get_price_history(ticker_symbol: str, period: str = "1y") -> list:
    """Get price history for chart. period: 1mo, 3mo, 6mo, 1y, 2y, 5y"""
    cache_key = f"history:{ticker_symbol.upper()}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period=period)

    data = []
    for date, row in hist.iterrows():
        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })

    cache.set(cache_key, data)
    return data


def get_risk_metrics(ticker_symbol: str, period: str = "3y") -> dict:
    """Calculate risk metrics: Sharpe, Sortino, Max Drawdown, Volatility."""
    cache_key = f"risk:{ticker_symbol.upper()}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period=period)

    if hist.empty or len(hist) < 30:
        return {"error": "Insufficient data"}

    closes = hist["Close"].values
    returns = np.diff(closes) / closes[:-1]

    # Annualized volatility
    vol = float(np.std(returns) * np.sqrt(252))

    # Annualized return
    total_return = (closes[-1] / closes[0]) - 1
    years = len(closes) / 252
    ann_return = float((1 + total_return) ** (1 / max(years, 0.01)) - 1)

    # Risk-free rate (approx 4.5%)
    rf = 0.045

    # Sharpe Ratio
    sharpe = (ann_return - rf) / vol if vol > 0 else 0

    # Sortino Ratio (downside deviation)
    neg_returns = returns[returns < 0]
    downside_dev = float(np.std(neg_returns) * np.sqrt(252)) if len(neg_returns) > 0 else 0.001
    sortino = (ann_return - rf) / downside_dev

    # Max Drawdown
    peak = closes[0]
    max_dd = 0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd

    # Current drawdown
    current_peak = max(closes)
    current_dd = float((current_peak - closes[-1]) / current_peak)

    result = {
        "volatility": round(vol * 100, 2),
        "annualized_return": round(ann_return * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "current_drawdown": round(current_dd * 100, 2),
        "total_return": round(total_return * 100, 2),
        "period": period,
    }

    cache.set(cache_key, result)
    return result


def get_dividend_history(ticker_symbol: str) -> list:
    """Get dividend payment history."""
    cache_key = f"dividends:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    divs = ticker.dividends

    if divs.empty:
        return []

    data = []
    for date, amount in divs.items():
        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "amount": round(float(amount), 4),
        })

    data.sort(key=lambda x: x["date"], reverse=True)
    cache.set(cache_key, data)
    return data


def get_fund_description(ticker_symbol: str) -> dict:
    """Get fund description and strategy."""
    cache_key = f"desc:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    result = {
        "description": info.get("longBusinessSummary", ""),
        "category": info.get("category", ""),
        "legal_type": info.get("legalType", ""),
        "fund_family": info.get("fundFamily", ""),
        "exchange": info.get("fullExchangeName", ""),
        "currency": info.get("currency", ""),
        "phone": info.get("phone", ""),
        "website": info.get("website", ""),
    }

    cache.set(cache_key, result)
    return result


def get_pre_post_market(ticker_symbol: str) -> dict:
    """Get pre-market and post-market data."""
    cache_key = f"prepost:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    result = {
        "pre_market_price": info.get("preMarketPrice"),
        "pre_market_change": round(info.get("preMarketChange", 0), 2) if info.get("preMarketChange") else None,
        "pre_market_change_pct": round(info.get("preMarketChangePercent", 0), 2) if info.get("preMarketChangePercent") else None,
        "pre_market_time": info.get("preMarketTime"),
        "post_market_price": info.get("postMarketPrice"),
        "post_market_change": round(info.get("postMarketChange", 0), 2) if info.get("postMarketChange") else None,
        "post_market_change_pct": round(info.get("postMarketChangePercent", 0), 2) if info.get("postMarketChangePercent") else None,
        "market_state": info.get("marketState", ""),
        "regular_market_price": info.get("regularMarketPrice"),
    }

    cache.set(cache_key, result)
    return result


def get_performance_comparison(symbols: list, period: str = "1y") -> dict:
    """Compare performance of multiple ETFs."""
    cache_key = f"perfcomp:{'_'.join(sorted(s.upper() for s in symbols))}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    all_data = {}
    for sym in symbols:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period=period)
        if hist.empty:
            continue
        closes = hist["Close"].values
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        # Normalize to percentage return from start
        base = closes[0]
        normalized = [round((c / base - 1) * 100, 2) for c in closes]
        all_data[sym.upper()] = {
            "dates": dates,
            "returns": normalized,
            "start_price": round(float(base), 2),
            "end_price": round(float(closes[-1]), 2),
            "total_return": round((closes[-1] / base - 1) * 100, 2),
        }

    result = {"period": period, "data": all_data}
    cache.set(cache_key, result)
    return result


def get_correlation(symbols: list, period: str = "1y") -> dict:
    """Calculate correlation matrix between ETFs."""
    cache_key = f"corr:{'_'.join(sorted(s.upper() for s in symbols))}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    returns_data = {}
    for sym in symbols:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period=period)
        if not hist.empty:
            closes = hist["Close"].values
            returns = np.diff(closes) / closes[:-1]
            returns_data[sym.upper()] = returns

    # Align lengths
    min_len = min(len(r) for r in returns_data.values()) if returns_data else 0
    for sym in returns_data:
        returns_data[sym] = returns_data[sym][-min_len:]

    syms = sorted(returns_data.keys())
    matrix = {}
    for s1 in syms:
        matrix[s1] = {}
        for s2 in syms:
            if s1 == s2:
                matrix[s1][s2] = 1.0
            else:
                corr = float(np.corrcoef(returns_data[s1], returns_data[s2])[0, 1])
                matrix[s1][s2] = round(corr, 4)

    result = {"symbols": syms, "correlation_matrix": matrix, "period": period}
    cache.set(cache_key, result)
    return result


def get_technical_indicators(ticker_symbol: str, period: str = "1y") -> dict:
    """Calculate technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands."""
    cache_key = f"tech:{ticker_symbol.upper()}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period=period)

    if hist.empty or len(hist) < 30:
        return {"error": "Insufficient data"}

    closes = hist["Close"].values
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]

    def sma(data, window):
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(None)
            else:
                result.append(round(float(np.mean(data[i-window+1:i+1])), 2))
        return result

    def ema(data, window):
        result = [None] * (window - 1)
        k = 2 / (window + 1)
        e = float(np.mean(data[:window]))
        result.append(round(e, 2))
        for i in range(window, len(data)):
            e = float(data[i]) * k + e * (1 - k)
            result.append(round(e, 2))
        return result

    def rsi(data, window=14):
        result = [None] * window
        for i in range(window, len(data)):
            changes = np.diff(data[i-window:i+1])
            gains = changes[changes > 0]
            losses = -changes[changes < 0]
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))
        return result

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    rsi14 = rsi(closes, 14)

    # MACD
    macd_line = []
    for i in range(len(ema12)):
        if ema12[i] is not None and ema26[i] is not None:
            macd_line.append(round(ema12[i] - ema26[i], 2))
        else:
            macd_line.append(None)

    # Signal line (9-day EMA of MACD)
    macd_valid = [x for x in macd_line if x is not None]
    macd_none_count = len(macd_line) - len(macd_valid)
    signal_line = [None] * macd_none_count
    if len(macd_valid) >= 9:
        k = 2 / 10
        e = float(np.mean(macd_valid[:9]))
        signal_line.append(round(e, 2))
        for i in range(9, len(macd_valid)):
            e = macd_valid[i] * k + e * (1 - k)
            signal_line.append(round(e, 2))
    else:
        signal_line = [None] * len(macd_line)

    # Ensure signal_line has same length as macd_line
    while len(signal_line) < len(macd_line):
        signal_line.append(None)
    signal_line = signal_line[:len(macd_line)]

    # Bollinger Bands (20-day)
    bb_upper = []
    bb_lower = []
    for i in range(len(closes)):
        if i < 19:
            bb_upper.append(None)
            bb_lower.append(None)
        else:
            window = closes[i-19:i+1]
            m = float(np.mean(window))
            s = float(np.std(window))
            bb_upper.append(round(m + 2 * s, 2))
            bb_lower.append(round(m - 2 * s, 2))

    # Downsample for frontend (every 3rd point for large datasets)
    step = max(1, len(dates) // 200)
    sample_idx = list(range(0, len(dates), step))
    if (len(dates) - 1) not in sample_idx:
        sample_idx.append(len(dates) - 1)

    result = {
        "dates": [dates[i] for i in sample_idx],
        "close": [round(float(closes[i]), 2) for i in sample_idx],
        "sma20": [sma20[i] for i in sample_idx],
        "sma50": [sma50[i] for i in sample_idx],
        "ema12": [ema12[i] for i in sample_idx],
        "ema26": [ema26[i] for i in sample_idx],
        "rsi14": [rsi14[i] for i in sample_idx],
        "macd": [macd_line[i] for i in sample_idx],
        "macd_signal": [signal_line[i] for i in sample_idx],
        "bb_upper": [bb_upper[i] for i in sample_idx],
        "bb_lower": [bb_lower[i] for i in sample_idx],
        "current_rsi": rsi14[-1] if rsi14[-1] else None,
    }

    cache.set(cache_key, result)
    return result


def get_top_movers(limit: int = 10) -> dict:
    """Get top gaining and losing ETFs today."""
    cache_key = f"movers:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    popular_etfs = [
        "SPY", "QQQ", "VOO", "VTI", "IVV", "VUG", "VTV", "IWF", "IWD",
        "VGT", "XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU",
        "XLRE", "XLC", "SOXX", "SMH", "ARKK", "GLD", "SLV", "TLT", "IEF",
        "HYG", "LQD", "BND", "AGG", "VNQ", "VXUS", "VEA", "VWO", "EEM",
        "IEMG", "IEMG", "SCHD", "VYM", "HDV", "NOBL", "DVY", "JEPI",
        "DRAM", "IBIT", "BITO", "SCHG", "SCHV", "IWB", "IWR", "IJR",
    ]
    popular_etfs = list(set(popular_etfs))

    gainers = []
    losers = []

    for sym in popular_etfs:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
            change = info.get("regularMarketChangePercent", 0)
            price = info.get("regularMarketPrice", 0)
            name = info.get("shortName", sym)
            volume = info.get("regularMarketVolume", 0)

            if change is not None and price:
                entry = {
                    "symbol": sym,
                    "name": name,
                    "price": round(float(price), 2),
                    "change_pct": round(float(change), 2),
                    "volume": int(volume) if volume else 0,
                }
                if change >= 0:
                    gainers.append(entry)
                else:
                    losers.append(entry)
        except Exception:
            continue

    gainers.sort(key=lambda x: x["change_pct"], reverse=True)
    losers.sort(key=lambda x: x["change_pct"])

    result = {
        "gainers": gainers[:limit],
        "losers": losers[:limit],
    }

    cache.set(cache_key, result)
    return result


def get_news(ticker_symbol: str) -> list:
    """Get news related to ETF."""
    cache_key = f"news:{ticker_symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ticker = yf.Ticker(ticker_symbol)
    news = ticker.news

    data = []
    for item in (news or [])[:10]:
        content = item.get("content", {})
        data.append({
            "title": content.get("title", item.get("title", "")),
            "summary": content.get("summary", ""),
            "url": content.get("canonicalUrl", {}).get("url", "") or item.get("link", ""),
            "publisher": content.get("provider", {}).get("displayName", "") or item.get("publisher", ""),
            "published": content.get("pubDate", ""),
            "thumbnail": content.get("thumbnail", {}).get("resolutions", [{}])[0].get("url", "") if content.get("thumbnail") else "",
        })

    cache.set(cache_key, data)
    return data


# Popular ETFs list for top movers
POPULAR_ETFS = [
    "SPY", "QQQ", "VOO", "VTI", "IVV", "VUG", "VTV", "IWF", "IWD",
    "VGT", "XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU",
    "XLRE", "XLC", "SOXX", "SMH", "ARKK", "GLD", "SLV", "TLT", "IEF",
    "HYG", "LQD", "BND", "AGG", "VNQ", "VXUS", "VEA", "VWO", "EEM",
]
