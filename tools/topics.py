"""Rough task/topic classifier for shortener links (rule-based, first match wins).
classify(url, alias, title, ip, resolve) -> (topic, kind); kind in task|probe|infra|baseline|other.
`resolve(host, alias)` returns the target URL of a nested short link in the same dataset (for chains)."""
import re
from urllib.parse import unquote
DATA_RULES = [  # (regex on decoded lowercase url, topic)
    (r'dataafrica', None),  # handled specially
    (r'api\.usa\.gov/crime|cde\.ucr\.cjis\.gov', 'FBI crime data (CDE)'),
    (r'worldpoverty\.io|internetpoverty\.io', 'World Poverty Clock (GraphQL)'),
    (r'sec\.gov.*county\.json|investor\.gov.*(county|regcf)|regcf_county|county\.json', 'SEC RegCF county.json'),
    (r'sec\.gov|investor\.gov', 'SEC / investor.gov (other files)'),
    (r'datausa\.io|api-la\.datausa', 'Data USA (workforce, tuition, poverty)'),
    (r'dataforindia', 'Data for India charts'),
    (r'nmdigital\.unm\.edu|nmdc\.unm\.edu|econtent\.unm\.edu', 'UNM Valmora digital collection'),
    (r'railroadtreasures|ebaydesc|ebay\.com', 'eBay / Railroad Magazine listings'),
    (r'mapgenie', 'MapGenie Palworld map API'),
    (r'howlongtobeat', 'HowLongToBeat game pages'),
    (r'hockey-reference', 'Hockey-Reference NSH 2023'),
    (r'technicalowl', 'NBA shot charts (technicalowl)'),
    (r'ons\.gov\.uk|nomisweb', 'UK census TS030 (ONS / Nomis)'),
    (r'airtable\.com', 'Airtable public view CSV'),
    (r'oec\.world', 'OEC trade data'),
    (r'worldbank\.org|datawheel', 'World Bank / Datawheel probes'),
    (r'nationsreportcard', 'NAEP Nation\'s Report Card'),
    (r'martingauer', 'GB emulator ROM (martingauer)'),
    (r'citybouldering|thisisyonder', 'Climbing prices (via Wayback)'),
    (r'cosmosmagazine|archive\.org\.au', 'Cosmos Magazine dinosaurs (via Wayback)'),
    (r'nypost\.com', 'NY Post Voynich manuscript'),
    (r'clarku\.edu|memgator', 'Clark Univ. economics newsletters (memento)'),
    (r'lcdl\.library\.cofc\.edu|catalogit', 'Charleston LCDL / CatalogIt archives'),
    (r'healthdata\.org|vizhub', 'IHME GBD (health)'),
    (r'oecd', 'OECD statistics'),
    (r'usaspending|max\.gov', 'usaspending / OMB budget'),
    (r'smilefm\.co\.za', 'smilefm.co.za WordPress REST'),
    (r'docs\.google\.com/viewerng|docs\.google\.com/gview', 'Google Docs viewer extraction'),
    (r'docs\.google\.com|drive\.google\.com', 'Google Docs / Drive documents'),
    (r'public\.tableau', 'Tableau Public dashboards'),
    (r'finance\.yahoo', 'Yahoo Finance history (TWLO)'),
    (r'bbmb\.gov\.in', 'BBMB power reports (India)'),
    (r'unctad', 'UNCTAD statistics'),
    (r'ihme|gapminder|unaids', 'Other health/dev statistics'),
    (r'github\.com/data-africa', 'Data Africa (citation / docs)'),
    (r'api\.census\.gov', 'US Census API (CPS ASEC)'),
    (r'code\.highcharts\.com', 'Highcharts map data (SEC county map)'),
    (r'googleusercontent\.com/viewer', 'Google Docs viewer extraction'),
    (r'api\.usa\.gov', 'api.usa.gov endpoint probes'),
]
PROXY = re.compile(r'jqp\.vercel\.app|md\.succ\.ai|markdown\.new|pure\.md|allorigins|corsmirror|r\.jina\.ai|workers\.dev|proxymule|webcrawlerapi|noroffcors|zcode\.appspot|translate\.goog|weserv\.nl|microlink|pretty-json|jsonhero|url2md|corsproxy|cors\.lol|cors-get-proxy')
SHORT = re.compile(r'https?://(?:www\.)?(vanderbi\.lt|da\.gd|is\.gd|v\.gd|tinyurl\.com|bitily\.in|2dd\.pl|yourls\.[a-z]+|hko\.nu)/([^/?&#\s]+)')
EVASION = re.compile(r'。|%61|%2e|%00|%09|@|\.nip\.io|xn--|https?://\d+\.\d+\.\d+\.\d+|\.\s*/|////|\.@', re.I)
def _decode(u):
    for _ in range(3):
        d = unquote(u)
        if d == u: break
        u = d
    return u.lower()
def _data_topic(d):
    if 'dataafrica' in d:
        if '/profile/' in d: return 'Data Africa: Malawi region profile pages'
        if not re.search(r'geo=0[45]0af\d|geo=040af', d): return 'Data Africa: API discovery & schema probes'
        if 'crop' in d or 'harvested' in d or 'sumlevel=lowest' in d:
            if '050af00152' in d: return 'Data Africa: Malawi crops (chickpea 2005)'
            if '050af00170' in d: return 'Data Africa: Mozambique rainfed crops'
            return 'Data Africa: crop surveys (other)'
        if '040af' in d or 'condition' in d or 'dhs' in d: return 'Data Africa: DHS child health (RW/TZ/GH)'
        return 'Data Africa: other geo queries'
    for rx, t in DATA_RULES[1:]:
        if re.search(rx, d): return t
    return None
def classify(url, alias='', title='', ip='', resolve=None, depth=0, service=''):
    if service == 'yourls.space': return 'yourls.space operator SEO spam (post-incident)', 'baseline'
    if ip.startswith(('129.59.', '10.55.')) or ip == '3.227.32.58' or re.search(r'vanderbilt\.edu|vumc\.org', url or '', re.I):
        return 'Site owner baseline (Vanderbilt)', 'baseline'
    d = _decode(url or ''); a = (alias or '').lower()
    if 'dataafrica' in d and EVASION.search(unquote(url or '')) and not re.search(r'https://api\.dataafrica\.io/', unquote(url or '')):
        return 'Host-parser evasion probes (Data Africa target)', 'probe'
    if re.search(r'httpbin(go)?\.org/base64|bing\.com/?$', d) or (a.endswith('txt') and 'httpbin' in d) or re.search(r'indexnow|bingvalid|keyverify|guidfile', a):
        return 'IndexNow / Bing key-file mimicry', 'probe'
    if re.search(r'yourls-api\.php|admin-ajax\.php|admin/index\.php|yourls\.(pro|website|biz|space)|dnscores|hko\.nu', d):
        return 'YOURLS scanning & chained writes', 'infra'
    if re.search(r'znotexist|union.*select|sqlmap|%27|\'\s*or\s', d): return 'Injection / error-oracle probes', 'probe'
    if re.search(r'wikiservice\.at|prowiki\.org', d): return 'Wiki relay pages (prowiki / wikiservice)', 'infra'
    if 'telegra.ph' in d: return 'telegra.ph publishing', 'infra'
    if re.search(r'counterapi|countapi', d): return 'CounterAPI covert counters', 'infra'
    t = _data_topic(d)
    if t: return t, 'task'
    # nested short link → follow the chain
    m = SHORT.search(unquote(url or ''))
    if m and resolve and depth < 3:
        inner = resolve(m.group(1).lower(), m.group(2))
        if inner:
            t2, k2 = classify(inner, '', '', '', resolve, depth + 1)
            if k2 == 'task': return t2, 'task'
            if t2 and k2 != 'other': return t2 + ' (via chain)', k2
        return 'Shortener chain (inner link not recoverable)', 'infra'
    if re.search(r'^https?://(www\.)?(example\.(com|org|net)|foo\.(com|org)|x\.(com|org)|google\.com|bing\.com|wikipedia\.org|en\.wikipedia\.org/wiki/test|httpbin\.org|httpbin\.io|api\.ipify\.org|example2\.com|dummy\d*\.org|github\.com|\d+\.\d+\.\d+\.\d+|x/?$|abc/?$|foo/?$|dead/?$|https?://)', d) or d in ('dead', 'data:text', 'javascript:deadbeef012345', 'mailto:deadbeef') or re.match(r'^(https?://)?(deadbeef|test)', d):
        return 'Canary / capability probes (example.com, httpbin…)', 'probe'
    if 'web.archive.org' in d or 'archive-it.org' in d: return 'Wayback reads (other targets)', 'task'
    if PROXY.search(d): return 'Reader-proxy chain (target unresolved)', 'infra'
    if not d or not d.startswith('http'): return 'Malformed / non-http targets', 'probe'
    return 'Other / unclassified', 'other'

def _inner(u):
    """first embedded http(s) URL after the outer host of a (decoded) proxy / wayback URL"""
    d = _decode_keep(u)
    m = re.match(r'https?://[^/?#]+', d)
    if not m: return None
    m2 = re.search(r'https?://', d[m.end():])
    return d[m.end() + m2.start():] if m2 else None
def _decode_keep(u):
    for _ in range(3):
        d = unquote(u)
        if d == u: break
        u = d
    return u
def leaf(url, resolve=None, depth=0):
    """Walk a target URL to its innermost host: unwrap reader proxies (jqp?url=…, allorigins raw?url=…, r.jina.ai/https://…),
    Wayback wrappers and short-link chains (`resolve(host, alias)` -> inner URL). Returns (leaf_host, depth, status) with
    status 'ok' | 'chain-lost' (short link whose target is unknown) | 'proxy-lost' (proxy call with no inner URL) | 'none'."""
    u = _decode_keep(url or '')
    m = re.match(r'https?://([^/?#]+)', u)
    if not m: return '', depth, 'none'
    h = m.group(1).lower().split('@')[-1].split(':')[0]
    if depth > 6: return h, depth, 'ok'
    if h == 'web.archive.org':
        inner = _inner(u)
        return leaf(inner, resolve, depth + 1) if inner else (h, depth, 'ok')
    sm = SHORT.match(u)
    if sm:
        inner = resolve(sm.group(1).lower(), sm.group(2)) if resolve else None
        if inner and _decode_keep(inner) != u: return leaf(inner, resolve, depth + 1)
        return h, depth, 'chain-lost'
    if PROXY.search(h):
        inner = _inner(u)
        if inner: return leaf(inner, resolve, depth + 1)
        return h, depth, 'proxy-lost'
    return h, depth, 'ok'
def chain(url, resolve=None, depth=0):
    """Like leaf() but returns the whole walk as a list of [kind, host]: kind in proxy | short | wayback | final | lost."""
    u = _decode_keep(url or '')
    m = re.match(r'https?://([^/?#]+)', u)
    if not m: return [['lost', '(no target)']]
    h = m.group(1).lower().split('@')[-1].split(':')[0]
    if depth > 6: return [['final', h]]
    if h == 'web.archive.org':
        inner = _inner(u)
        return [['wayback', h]] + (chain(inner, resolve, depth + 1) if inner else [])
    sm = SHORT.match(u)
    if sm:
        inner = resolve(sm.group(1).lower(), sm.group(2)) if resolve else None
        if inner and _decode_keep(inner) != u: return [['short', h]] + chain(inner, resolve, depth + 1)
        return [['short', h], ['lost', '(target unrecoverable)']]
    if PROXY.search(h):
        inner = _inner(u)
        if inner: return [['proxy', h]] + chain(inner, resolve, depth + 1)
        return [['proxy', h], ['lost', '(no inner URL)']]
    return [['final', h]]
