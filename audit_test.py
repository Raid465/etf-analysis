import requests, time

BASE = 'http://localhost:8000'
PASS = 0
FAIL = 0
TIMEOUT = 5

def test(name, condition, sev='Low', note=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'[PASS] {name}')
    else:
        FAIL += 1
        print(f'[FAIL][{sev}] {name} | {note}')

def api(method, path, **kw):
    try:
        r = requests.request(method, f'{BASE}{path}', timeout=TIMEOUT, **kw)
        return r
    except Exception as e:
        return None

start = time.time()

# ===== FRONTEND =====
r = api('GET', '/')
test('Homepage 200', r and r.status_code == 200, 'Critical')
test('RTL', r and 'rtl' in r.text, 'Medium')
test('All tabs', r and all(t in r.text for t in ['تحليل','مقارنة','صناديق']), 'Medium')
test('Dividends section', r and 'التوزيعات السنوية' in r.text, 'Medium')
test('Holdings canvas', r and 'ch-saudi-holdings' in r.text, 'Medium')
test('Fund holdings canvas', r and 'ch-fund-holdings' in r.text, 'Medium')
test('Empty msg', r and 'لا توجد بيانات توزيعات' in r.text, 'Medium')

# ===== API =====
test('GET /api/saudi/list 200', (r:=api('GET','/api/saudi/list')) and r.status_code==200, 'High')
test('GET /api/mutual-funds 200', (r:=api('GET','/api/mutual-funds')) and r.status_code==200, 'High')
test('GET /api/mutual-funds/stats 200', (r:=api('GET','/api/mutual-funds/stats')) and r.status_code==200, 'High')
test('GET /api/mutual-funds/009003 200', (r:=api('GET','/api/mutual-funds/009003')) and r.status_code==200, 'High')
test('GET /api/mutual-funds/009003/holdings 200', (r:=api('GET','/api/mutual-funds/009003/holdings')) and r.status_code==200, 'High')
test('GET /api/mutual-funds/INVALID 404', (r:=api('GET','/api/mutual-funds/INVALID')) and r.status_code==404, 'High')

# Pagination
r = api('GET', '/api/mutual-funds?page=1&page_size=10')
test('Pagination total>300', r and r.json().get('total',0) > 300, 'High')
test('Pagination page_size=10', r and len(r.json().get('funds',[])) == 10, 'Medium')
test('Has filters', r and 'currencies' in r.json().get('filters',{}), 'Low')

# Dividends
for sym, expect in [('4342','has'),('009003','has'),('9400','zero'),('INVALID','zero')]:
    r = api('GET', f'/api/saudi/dividends/{sym}')
    if r:
        d = r.json()
        has = len(d.get('distributions',[])) > 0
        ok = has if expect == 'has' else not has
        test(f'Dividends {sym}: {expect}', ok, 'Medium', f'{len(d.get("distributions",[]))} dists')

# ===== SECURITY =====
test('GET /.env blocked', (r:=api('GET','/.env',allow_redirects=False)) and r.status_code in [404,403], 'Critical')
test('GET /cache.db blocked', (r:=api('GET','/cache.db',allow_redirects=False)) and r.status_code in [404,403], 'Critical')
test('GET /../etc/passwd blocked', (r:=api('GET','/../etc/passwd',allow_redirects=False)) and r.status_code!=200, 'Critical')

# XSS
r = api('GET', '/api/mutual-funds?search=<script>alert(1)</script>')
test('XSS filtered', r and '<script>alert(1)</script>' not in r.text, 'Critical')

# Security headers
r = api('GET', '/')
for h in ['X-Content-Type-Options','X-Frame-Options','Content-Security-Policy']:
    test(f'Has {h}', r and h in r.headers, 'Medium')

# ===== ERROR HANDLING =====
for path in ['/api/compare','/api/portfolio/save']:
    r = api('POST', path, data='not json', headers={'Content-Type':'application/json'})
    test(f'{path} bad JSON 422', r and r.status_code in [400,422,415], 'Medium')
    r = api('POST', path, data='{}', headers={'Content-Type':'application/json'})
    test(f'{path} empty body 400/422', r and r.status_code in [400,422], 'Medium')

# ===== PERFORMANCE =====
for name, path in [('Home','/'),('Funds API','/api/mutual-funds'),('Dividends','/api/saudi/dividends/4342')]:
    times = []
    for _ in range(3):
        t = time.time()
        api('GET', path)
        times.append(time.time() - t)
    avg = sum(times)/len(times)
    test(f'{name} avg {avg*1000:.0f}ms', avg < 0.5, 'Medium' if avg<1 else 'Low', f'{avg*1000:.0f}ms')

elapsed = time.time() - start
total = PASS + FAIL
pct = round(PASS/total*100,1) if total else 0
print(f'\n=== DONE ({elapsed:.0f}s) ===')
print(f'Pass: {PASS}/{total} ({pct}%) | Fail: {FAIL}')
