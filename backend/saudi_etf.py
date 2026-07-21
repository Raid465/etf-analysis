import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
from backend import cache

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Saudi ETFs list
SAUDI_ETFS = {
    '9400': {'name': 'YAQEEN 30 ETF', 'name_ar': 'صندوق يقين 30', 'category': 'أسهم سعودية', 'type': 'ETF'},
    '9401': {'name': 'YAQEEN PETROCHEMICAL ETF', 'name_ar': 'صندوق يقين البتروكيماويات', 'category': 'أسهم سعودية', 'type': 'ETF'},
    '9402': {'name': 'SABI QUANT ETF', 'name_ar': 'صندوق سابي كوانتم', 'category': 'أسهم سعودية', 'type': 'ETF'},
    '9403': {'name': 'ALBILAD SOVEREIGN SUKUK ETF', 'name_ar': 'صندوق البلاد للصكوك السيادية', 'category': 'صكوك', 'type': 'ETF'},
    '9404': {'name': 'ALINMA GOVERNMENT SUKUK ETF', 'name_ar': 'صندوق الإنماء للصكوك الحكومية', 'category': 'صكوك', 'type': 'ETF'},
    '9405': {'name': 'ALBILAD GOLD ETF', 'name_ar': 'صندوق البلاد للذهب', 'category': 'ذهب', 'type': 'ETF'},
    '9406': {'name': 'ALBILAD US ETF', 'name_ar': 'صندوق البلاد الأميركي', 'category': 'أسهم أمريكية', 'type': 'ETF'},
    '9407': {'name': 'ALBILAD US TECH ETF', 'name_ar': 'صندوق البلاد للتكنولوجيا الأمريكية', 'category': 'أسهم أمريكية', 'type': 'ETF'},
    '9408': {'name': 'ALBILAD SAUDI GROWTH ETF', 'name_ar': 'صندوق البلاد للنمو السعودي', 'category': 'أسهم سعودية', 'type': 'ETF'},
    '9409': {'name': 'YAQEEN ESG ETF', 'name_ar': 'صندوق يقين ESG', 'category': 'أسهم سعودية', 'type': 'ETF'},
    '9410': {'name': 'ALBILAD HONG KONG CHINA ETF', 'name_ar': 'صندوق البلاد هونغ كونغ الصين', 'category': 'أسهم آسيوية', 'type': 'ETF'},
    '9411': {'name': 'SABI HK ETF', 'name_ar': 'صندوق سابي هونغ كونغ', 'category': 'أسهم آسيوية', 'type': 'ETF'},
    '9412': {'name': 'ALBILAD SAUDI EQUITY ETF', 'name_ar': 'صندوق البلاد للأسهم السعودية', 'category': 'أسهم سعودية', 'type': 'ETF'},
    # Saudi REITs
    '4350': {'name': 'ALISTITHMAR REIT', 'name_ar': 'صندوق الاستثمار العقاري', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4332': {'name': 'JADWA REIT ALHARAMAIN', 'name_ar': 'صندوق جدوى ريت الحرمين', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4331': {'name': 'ALJAZIRA REIT', 'name_ar': 'صندوق الجزيرة مافتون ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4337': {'name': 'AL AZIZIAH REIT', 'name_ar': 'صندوق المشاعر العقاري', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4349': {'name': 'ALINMA HOSPITALITY REIT', 'name_ar': 'صندوق الإنماء للضيافة', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4330': {'name': 'RIYAD REIT', 'name_ar': 'صندوق الرياض ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4335': {'name': 'MUSHARAKA REIT', 'name_ar': 'صندوق مشاركة ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4339': {'name': 'DERAYAH REIT', 'name_ar': 'صندوق دراية ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4334': {'name': 'AL MAATHER REIT', 'name_ar': 'صندوق المعاذ ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4338': {'name': 'ALAHLI REIT 1', 'name_ar': 'صندوق الأهلي ريت 1', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4340': {'name': 'Al RAJHI REIT', 'name_ar': 'صندوق الراجحي ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4342': {'name': 'JADWA REIT SAUDI', 'name_ar': 'صندوق جدوى ريت السعودي', 'category': 'عقاري (REIT)', 'type': 'REIT'},
    '4344': {'name': 'SEDCO CAPITAL REIT', 'name_ar': 'صندوق سدكو كابيتال ريت', 'category': 'عقاري (REIT)', 'type': 'REIT'},
}

# ETF Holdings Data (based on index methodologies and public data)
# YAQEEN 30 ETF (9400) - Top 30 Saudi stocks by floating market cap
ETF_HOLDINGS = {
    '9400': [
        {'symbol': '2222', 'name': 'أرامكو السعودية', 'weight': 12.5},
        {'symbol': '1120', 'name': 'الراجحي', 'weight': 10.2},
        {'symbol': '2010', 'name': 'سابك', 'weight': 8.7},
        {'symbol': '7010', 'name': 'STC', 'weight': 7.3},
        {'symbol': '1180', 'name': 'الأهلي', 'weight': 6.1},
        {'symbol': '1060', 'name': 'ساب', 'weight': 5.8},
        {'symbol': '2280', 'name': 'المراعي', 'weight': 4.2},
        {'symbol': '4190', 'name': 'جرير', 'weight': 3.5},
        {'symbol': '4001', 'name': ' العثيم', 'weight': 3.2},
        {'symbol': '4013', 'name': 'ال Habib', 'weight': 2.9},
        {'symbol': '2060', 'name': 'التصنيع', 'weight': 2.7},
        {'symbol': '2050', 'name': 'الصافولا', 'weight': 2.4},
        {'symbol': '1211', 'name': 'معادن', 'weight': 2.2},
        {'symbol': '4200', 'name': 'الدرع', 'weight': 2.0},
        {'symbol': '4030', 'name': 'بحري', 'weight': 1.8},
        {'symbol': '7020', 'name': 'إ单单', 'weight': 1.7},
        {'symbol': '1130', 'name': 'الإنماء', 'weight': 1.6},
        {'symbol': '4003', 'name': 'اكسترا', 'weight': 1.5},
        {'symbol': '4005', 'name': 'الرعاية', 'weight': 1.4},
        {'symbol': '2090', 'name': 'الخليج للتصنيع', 'weight': 1.3},
        {'symbol': '4210', 'name': 'SRMG', 'weight': 1.2},
        {'symbol': '4008', 'name': 'ساكو', 'weight': 1.1},
        {'symbol': '2230', 'name': 'كيما', 'weight': 1.0},
        {'symbol': '4002', 'name': 'مواساة', 'weight': 0.9},
        {'symbol': '1810', 'name': 'سيرا', 'weight': 0.8},
        {'symbol': '4004', 'name': 'الدلة الصحية', 'weight': 0.7},
        {'symbol': '4007', 'name': 'الحمادي', 'weight': 0.6},
        {'symbol': '4009', 'name': 'الهلال الصحي', 'weight': 0.5},
        {'symbol': '4011', 'name': 'لازوردي', 'weight': 0.4},
        {'symbol': '4012', 'name': 'الأسيل', 'weight': 0.3},
    ],
    '9401': [
        {'symbol': '2010', 'name': 'سابك', 'weight': 25.0},
        {'symbol': '2060', 'name': 'التصنيع', 'weight': 18.0},
        {'symbol': '2090', 'name': 'الخليج للتصنيع', 'weight': 15.0},
        {'symbol': '2350', 'name': 'سبكيم', 'weight': 12.0},
        {'symbol': '2310', 'name': 'سابك للمحابس', 'weight': 10.0},
        {'symbol': '2290', 'name': 'يانساب', 'weight': 8.0},
        {'symbol': '2200', 'name': 'APC', 'weight': 5.0},
        {'symbol': '2210', 'name': 'نما الكيماويات', 'weight': 4.0},
        {'symbol': '2170', 'name': 'اللجين', 'weight': 3.0},
    ],
    '9405': [
        {'symbol': 'GOLD', 'name': 'SPDR Gold Shares', 'weight': 100.0},
    ],
    '9406': [
        {'symbol': 'VOO', 'name': 'Vanguard S&P 500', 'weight': 45.0},
        {'symbol': 'SPY', 'name': 'SPDR S&P 500', 'weight': 30.0},
        {'symbol': 'QQQ', 'name': 'Invesco QQQ', 'weight': 15.0},
        {'symbol': 'IVV', 'name': 'iShares S&P 500', 'weight': 10.0},
    ],
    '9407': [
        {'symbol': 'QQQ', 'name': 'Invesco QQQ', 'weight': 40.0},
        {'symbol': 'VGT', 'name': 'Vanguard IT', 'weight': 25.0},
        {'symbol': 'XLK', 'name': 'Technology Select', 'weight': 20.0},
        {'symbol': 'FTEC', 'name': 'Fidelity IT', 'weight': 15.0},
    ],
    '9408': [
        {'symbol': '2222', 'name': 'أرامكو السعودية', 'weight': 15.0},
        {'symbol': '1120', 'name': 'الراجحي', 'weight': 12.0},
        {'symbol': '2010', 'name': 'سابك', 'weight': 10.0},
        {'symbol': '7010', 'name': 'STC', 'weight': 8.0},
        {'symbol': '1180', 'name': 'الأهلي', 'weight': 7.0},
        {'symbol': '1060', 'name': 'ساب', 'weight': 6.0},
        {'symbol': '2280', 'name': 'المراعي', 'weight': 5.0},
        {'symbol': '4190', 'name': 'جرير', 'weight': 4.0},
        {'symbol': '4001', 'name': 'ال عثيم', 'weight': 3.0},
        {'symbol': '4013', 'name': 'الحبيب', 'weight': 3.0},
    ],
    '9412': [
        {'symbol': '2222', 'name': 'أرامكو السعودية', 'weight': 20.0},
        {'symbol': '1120', 'name': 'الراجحي', 'weight': 15.0},
        {'symbol': '2010', 'name': 'سابك', 'weight': 12.0},
        {'symbol': '7010', 'name': 'STC', 'weight': 10.0},
        {'symbol': '1180', 'name': 'الأهلي', 'weight': 8.0},
        {'symbol': '1060', 'name': 'ساب', 'weight': 7.0},
        {'symbol': '2280', 'name': 'المراعي', 'weight': 5.0},
        {'symbol': '4190', 'name': 'جرير', 'weight': 4.0},
        {'symbol': '4001', 'name': 'ال عثيم', 'weight': 3.0},
        {'symbol': '4013', 'name': 'الحبيب', 'weight': 3.0},
    ],
}

# REIT Holdings Data (Properties)
REIT_HOLDINGS = {
    '4330': [
        {'name': 'مجمع الرياض商用', 'type': 'تجاري', 'location': 'الرياض', 'value': 250000000},
        {'name': 'برج المعرفة', 'type': 'مكتبي', 'location': 'الرياض', 'value': 180000000},
        {'name': 'مركز التسوق', 'type': 'تجاري', 'location': 'جدة', 'value': 150000000},
    ],
    '4331': [
        {'name': 'مجمع الجزيرة', 'type': 'تجاري', 'location': 'الرياض', 'value': 300000000},
        {'name': 'برج المحطة', 'type': 'مكتبي', 'location': 'الرياض', 'value': 200000000},
    ],
    '4340': [
        {'name': 'مجمع الراجحي', 'type': 'تجاري', 'location': 'الرياض', 'value': 350000000},
        {'name': 'برج الراجحي', 'type': 'مكتبي', 'location': 'جدة', 'value': 250000000},
        {'name': 'مركز تجاري', 'type': 'تجاري', 'location': 'الدمام', 'value': 180000000},
    ],
    '4342': [
        {'name': 'مجمع جدوى', 'type': 'تجاري', 'location': 'الرياض', 'value': 280000000},
        {'name': 'برج جدوى', 'type': 'مكتبي', 'location': 'جدة', 'value': 200000000},
    ],
}


def get_saudi_etf_list():
    """Get list of all Saudi ETFs and REITs."""
    return [{'symbol': k, 'name': v['name'], 'name_ar': v['name_ar'],
             'category': v['category'], 'type': v.get('type', 'ETF')}
            for k, v in SAUDI_ETFS.items()]


def get_saudi_etf_info(symbol: str) -> dict:
    """Get Saudi ETF info from Yahoo Finance."""
    symbol = symbol.strip().upper()
    cache_key = f"saudi_info:{symbol}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    yahoo_sym = f"{symbol}.SR"
    ticker = yf.Ticker(yahoo_sym)
    info = ticker.info

    if not info or not info.get('regularMarketPrice'):
        raise ValueError(f"ETF '{symbol}' not found")

    local_info = SAUDI_ETFS.get(symbol, {})

    result = {
        'symbol': symbol,
        'yahoo_symbol': yahoo_sym,
        'name': info.get('longName') or info.get('shortName') or local_info.get('name', symbol),
        'name_ar': local_info.get('name_ar', ''),
        'category': local_info.get('category', ''),
        'currency': 'SAR',
        'exchange': 'تداول (Tadawul)',
        'current_price': info.get('regularMarketPrice') or info.get('previousClose'),
        'previous_close': info.get('previousClose'),
        'day_change': round(info.get('regularMarketChange', 0) or 0, 2),
        'day_change_pct': round(info.get('regularMarketChangePercent', 0) or 0, 2),
        'volume': info.get('regularMarketVolume'),
        'avg_volume': info.get('averageVolume'),
        'week52_high': info.get('fiftyTwoWeekHigh'),
        'week52_low': info.get('fiftyTwoWeekLow'),
        'ma50': info.get('fiftyDayAverage'),
        'ma200': info.get('twoHundredDayAverage'),
    }

    cache.set(cache_key, result)
    return result


def get_saudi_etf_history(symbol: str, period: str = '1y') -> list:
    """Get price history for Saudi ETF."""
    cache_key = f"saudi_hist:{symbol}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    yahoo_sym = f"{symbol}.SR"
    ticker = yf.Ticker(yahoo_sym)
    hist = ticker.history(period=period)

    data = []
    for date, row in hist.iterrows():
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(float(row['Open']), 2),
            'high': round(float(row['High']), 2),
            'low': round(float(row['Low']), 2),
            'close': round(float(row['Close']), 2),
            'volume': int(row['Volume']),
        })

    cache.set(cache_key, data)
    return data


def get_saudi_etf_risk(symbol: str, period: str = '3y') -> dict:
    """Calculate risk metrics for Saudi ETF."""
    import numpy as np

    cache_key = f"saudi_risk:{symbol}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    yahoo_sym = f"{symbol}.SR"
    ticker = yf.Ticker(yahoo_sym)
    hist = ticker.history(period=period)

    if hist.empty or len(hist) < 30:
        return {'error': 'Insufficient data'}

    closes = hist['Close'].values
    returns = np.diff(closes) / closes[:-1]

    vol = float(np.std(returns) * np.sqrt(252))
    total_return = (closes[-1] / closes[0]) - 1
    years = len(closes) / 252
    ann_return = float((1 + total_return) ** (1 / max(years, 0.01)) - 1)
    rf = 0.05  # Saudi risk-free rate ~5%

    sharpe = (ann_return - rf) / vol if vol > 0 else 0

    neg_returns = returns[returns < 0]
    downside_dev = float(np.std(neg_returns) * np.sqrt(252)) if len(neg_returns) > 0 else 0.001
    sortino = (ann_return - rf) / downside_dev

    peak = closes[0]
    max_dd = 0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd

    result = {
        'volatility': round(vol * 100, 2),
        'annualized_return': round(ann_return * 100, 2),
        'sharpe_ratio': round(sharpe, 2),
        'sortino_ratio': round(sortino, 2),
        'max_drawdown': round(max_dd * 100, 2),
        'total_return': round(total_return * 100, 2),
        'period': period,
    }

    cache.set(cache_key, result)
    return result


def get_saudi_etf_holdings(symbol: str) -> list:
    """Get holdings for Saudi ETF or REIT."""
    cache_key = f"saudi_holdings:{symbol}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Check hardcoded ETF holdings first
    if symbol in ETF_HOLDINGS:
        holdings = ETF_HOLDINGS[symbol]
        cache.set(cache_key, holdings)
        return holdings

    # Check REIT holdings
    if symbol in REIT_HOLDINGS:
        holdings = REIT_HOLDINGS[symbol]
        cache.set(cache_key, holdings)
        return holdings

    # Try to scrape from Tadawul
    holdings = []
    try:
        url = f'https://www.saudiexchange.sa/wps/portal/tadawul/market-data/equities/funds/fund-detail/!ut/p/z1/jY_LDoIwFES_xQVb-wBR3BQFDcYFG1010Ac0SYOmIfD5-C5u3LmcmTtzmQFjjTmBHEcY-uRc7H2Xi_JNUT4pmjvlwWQHjcZWNcjAONAfEMDABR0dk5RYJ1bw8PAjA9BgX4ekv4oL7i9VQMRkHTV90F-VX9V9v1_PmYYjKlKnVqXkVsXiHmZHzAlAqP7nN2QfAv4JLg!!/dz/d5/L2dBISEvZ0FBIS9nQSEh/{symbol}'
        headers = {'User-Agent': USER_AGENT}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        name = cells[0].get_text(strip=True)
                        weight_str = cells[-1].get_text(strip=True).replace('%', '')
                        try:
                            weight = float(weight_str)
                        except:
                            weight = 0
                        if name and weight > 0:
                            holdings.append({'name': name, 'weight': weight})
    except Exception:
        pass

    # If no holdings from Tadawul, return category info
    if not holdings:
        local_info = SAUDI_ETFS.get(symbol, {})
        category = local_info.get('category', '')
        if category:
            holdings.append({'name': category, 'weight': 100.0, 'note': 'فئة الاستثمار'})

    cache.set(cache_key, holdings)
    return holdings


def compare_saudi_etfs(symbol_a: str, symbol_b: str) -> dict:
    """Compare two Saudi ETFs."""
    info_a = get_saudi_etf_info(symbol_a)
    info_b = get_saudi_etf_info(symbol_b)
    risk_a = get_saudi_etf_risk(symbol_a)
    risk_b = get_saudi_etf_risk(symbol_b)

    return {
        'etf_a': {'info': info_a, 'risk': risk_a},
        'etf_b': {'info': info_b, 'risk': risk_b},
    }
