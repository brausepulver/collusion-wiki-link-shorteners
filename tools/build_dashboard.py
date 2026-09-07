#!/usr/bin/env python3
"""Assemble dashboard/data.json from raw_artifacts + db_extracts, then inject into dashboard/template.html -> dashboard/index.html"""
import csv, json, glob, os, collections, re, time
from urllib.parse import urlsplit, unquote
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from topics import classify
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
WINDOW_START = '2026-05-01'
def host_of(u):
    try:
        h = (urlsplit(u).hostname or '').lower()
        if not h and u.startswith(('http%3a', 'https%3a')): h = (urlsplit(unquote(u)).hostname or '').lower()
        return h
    except Exception: return ''
# --- creator-IP origin (ASN via Team Cymru, Azure region via Service Tags; produced by tools/lookup_ip_origin.py) ---
ORIGIN = json.load(open('raw_artifacts/ip_origin/ip_origin.json')) if os.path.exists('raw_artifacts/ip_origin/ip_origin.json') else {'meta': {}, 'ips': {}}
GROUP_BY_ASN = {8075: 'azure', 16509: 'aws', 14618: 'aws', 396982: 'gcp', 15169: 'gcp', 13335: 'cloudflare', 132892: 'cloudflare',
                14061: 'hosting', 212317: 'hosting', 24940: 'hosting', 400940: 'hosting', 9123: 'hosting'}
def short_org(org):
    """'AMAZON-02 - Amazon.com, Inc., US' -> 'Amazon.com (US)'"""
    org = org.split(' - ', 1)[-1]
    org, _, cc = org.rpartition(', ')
    org = re.sub(r',?\s*(Inc\b\.?|LLC|GmbH|PTE\.?\s*LTD\.?|JSC|Corporation|Online)\s*', ' ', org, flags=re.I).replace('_', '').strip(' ,.')
    return re.sub(r'\s+', ' ', org) + (f' ({cc})' if cc else '')
def origin(ip):
    """-> (group, azure_region, org). group: azure|aws|gcp|cloudflare|hosting|isp|vanderbilt|other"""
    if ip.startswith('129.59.') or ip.startswith('10.55.'): return 'vanderbilt', '', 'Vanderbilt University'
    r = ORIGIN['ips'].get(ip)
    if not r or 'asn' not in r: return 'other', '', ''
    g = GROUP_BY_ASN.get(r['asn'])
    if not g: g = 'isp' if not re.search(r'cloud|hosting|server|datacenter|vps', r['org'], re.I) else 'hosting'
    return g, r.get('region', ''), short_org(r['org'])
SERVICES = []
LINKS = []     # detailed rows in window
DAILY = {}     # service -> {date: n} full history
# YOURLS stamps links in the server's local time, not UTC. vanderbi.lt sits in Nashville: the 20 links the wiki cites were
# "created" exactly 300 min before the citing revision, and the hourly profile correlates with wiki writes at +5h (0.91) vs +6h (0.54).
# Convert to UTC at load time so every time in the dashboard is comparable with the wiki DB and Wayback. Other instances: unknown, left as-is.
from datetime import datetime
from zoneinfo import ZoneInfo
SERVER_TZ = {'vanderbi.lt': 'America/Chicago'}
def to_utc(ts, tz):
    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%d %H:%M:%S')
def load_yourls(sid, dirs):
    rows = {}
    stats = None; fetched = None; api = None; ua = None; pages = []; kind = None; extra = collections.Counter()
    for d in dirs:
        p = os.path.join(d, 'links.csv')
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p)):
            if sid in SERVER_TZ: r['timestamp'] = to_utc(r['timestamp'], SERVER_TZ[sid])
            rows[r['alias']] = r
        m = json.load(open(os.path.join(d, 'meta.json')))
        stats = m.get('stats') or stats; fetched = m.get('fetched_at'); api = m.get('api'); ua = m.get('user_agent'); kind = m.get('kind') or kind
        pages += [os.path.relpath(os.path.join(d, 'pages', x), ROOT) for x in sorted(os.listdir(os.path.join(d, 'pages')))] if os.path.isdir(os.path.join(d, 'pages')) else []
        dc = os.path.join(d, 'daily_counts.json')  # public export (tools/public_export.py): per-day counts of rows held out of the published ledger
        if os.path.exists(dc): extra.update(json.load(open(dc)))
    if not rows: return
    daily = collections.Counter(r['timestamp'][:10] for r in rows.values())
    daily.update(extra)
    DAILY[sid] = dict(sorted(daily.items()))
    nwin = 0
    for a, r in rows.items():
        if r['timestamp'] < WINDOW_START: continue
        nwin += 1
        og = origin(r['ip'])
        LINKS.append(dict(s=sid, a=a, t=r['timestamp'], ip=r['ip'], c=int(r['clicks'] or 0), h=host_of(r['url']), u=r['url'][:600],
                          ti=(r['title'] or '')[:200] if r['title'] != r['url'] else '', cl=og[0], rg=og[1], an=og[2], su=r.get('shorturl') or f'https://{sid}/{a}'))
    SERVICES.append(dict(id=sid, kind=kind or 'YOURLS (open stats API)', api=api, user_agent=ua, fetched_at=fetched, stats=stats,
                         server_tz=SERVER_TZ.get(sid), tz_note=('raw stamps are server local time (%s); converted to UTC here' % SERVER_TZ[sid]) if sid in SERVER_TZ else 'raw stamps kept as served; server timezone unknown',
                         n_fetched=len(rows), n_window=nwin, oldest=min(r['timestamp'] for r in rows.values()), newest=max(r['timestamp'] for r in rows.values()),
                         raw_files=[os.path.relpath(os.path.join(d, 'links.csv'), ROOT) for d in dirs if os.path.exists(os.path.join(d, 'links.csv'))] + pages[:3] + (['… %d page files' % len(pages)] if len(pages) > 3 else pages[3:])))
load_yourls('vanderbi.lt', ['raw_artifacts/shorteners/vanderbi.lt', 'raw_artifacts/shorteners/vanderbi.lt_tail'])
for d in sorted(glob.glob('raw_artifacts/shorteners/*/links.csv')):
    sid = d.split('/')[2]
    if sid.startswith('vanderbi.lt'): continue
    load_yourls(sid, [os.path.dirname(d)])
# --- wiki-derived rows for shorteners with no listing API (tinyurl, is.gd, v.gd, da.gd, ctxr.me, 2dd.pl, wiped bitily.in aliases) ---
# No creation time, creator IP or click count is exposed by these services. Each alias the wiki cites becomes one row whose
# time is the FIRST wiki citation (an upper bound for creation) and whose "IP" is the citing revision's /16 (the DB stores no
# full IPs). Aliases seen only as vanderbi.lt targets (chains) take the vanderbi.lt link's UTC time and real creator IP.
# Rows carry ap='wiki'|'chain' so the UI can exclude them from creator-IP counts. da.gd rows get the 60-day access total
# from tools/fetch_dagd_stats.py; Wayback capture counts come from tools/cdx_aliases.py.
IP16_ASN = {}
if os.path.exists('raw_artifacts/sweep2/asn/ip16_asn.tsv'):
    for r in csv.DictReader(open('raw_artifacts/sweep2/asn/ip16_asn.tsv'), delimiter='\t'): IP16_ASN[r['ip16']] = r
def origin16(ip16):
    r = IP16_ASN.get(ip16)
    if not r or not r.get('asn', '').isdigit(): return 'other', '', ''
    asn = int(r['asn']); g = GROUP_BY_ASN.get(asn)
    if not g: g = 'isp' if not re.search(r'cloud|hosting|server|datacenter|vps', r['as_org'], re.I) else 'hosting'
    return g, '', short_org(r['as_org'])
DAGD = json.load(open('raw_artifacts/shorteners/da.gd/stats.json')) if os.path.exists('raw_artifacts/shorteners/da.gd/stats.json') else None
WB = json.load(open('raw_artifacts/shorteners/wayback_aliases.json')) if os.path.exists('raw_artifacts/shorteners/wayback_aliases.json') else None
def wb_of(short_url):
    rec = (WB or {}).get('links', {}).get(short_url)
    if not rec or 'n' not in rec: return None
    caps = rec['captures']; first = caps[0] if caps else {}
    return dict(n=rec['n'], first=rec.get('first', ''), last=rec.get('last', ''), st=first.get('statuscode', ''), tgt=(first.get('redirect') or '')[:300],
                inwin=sum(1 for c in caps if '20260501' <= c['timestamp'][:8] <= '20260731'))
YOURLS_HOSTS = ('vanderbi.lt', 'bitily.in', '2dd.pl', 'yourls.pro', 'yourls.website', 'yourls.space')
def akey(host, alias, url=''):
    """(host, alias) as cited -> key that matches the ledger row: YOURLS keywords are case-insensitive, '#…'/'&…' tails are
    wiki-markup residue; ctxr.me 'aliases' are whole URLs (ctxr.me/https://example.com), so keep the full path there."""
    if host == 'ctxr.me' and url: alias = urlsplit(url).path.strip('/')
    a = re.split(r'[#&]', alias)[0]
    if host in YOURLS_HOSTS: a = a.lower()
    if host == 'bitily.in' and a.startswith('mylabi/'): a = 'MYLABI/' + a[7:]
    return (host, a)
_mentions_all = json.load(open('db_extracts/shortlink_mentions.json'))
if os.path.exists('db_extracts/jd_shortlink_mentions.json'):  # citations found in JoshuaDavid's wiki exports that our DB lacks (wiki4d, paste sites, late probier revisions)
    _mentions_all += [dict(m, ip16=m.get('ip16') or '') for m in json.load(open('db_extracts/jd_shortlink_mentions.json'))['mentions'] if m.get('time')]
def _cite_note(m): return ('cited in JoshuaDavid export %s/%s (%s)' % (m['wiki'], m['page'], m['label'])) if m.get('found_in') == 'jd-agent-logs' else ''
_first_mention = {}
for m in _mentions_all:
    k = akey(m['host'], m['alias'], m['url'])
    if k not in _first_mention or m['time'] < _first_mention[k]['time']: _first_mention[k] = m
_vd_chain = {}  # (host, alias) -> vanderbi.lt link that targets it
for l in LINKS:
    if l['s'] != 'vanderbi.lt': continue
    p = urlsplit(l['u']).path.strip('/')
    if l['h'] and p and 'yourls-api' not in p and 'admin' not in p:
        k = (l['h'], p.split('/')[0] if l['h'] != 'bitily.in' else '/'.join(p.split('/')[:2]))
        if k not in _vd_chain or l['t'] < _vd_chain[k]['t']: _vd_chain[k] = l
_have = {akey(l['s'], l['a']) for l in LINKS} | {('bitily.in', 'MYLABI/' + l['a']) for l in LINKS if l['s'] == 'bitily.in_wayback'} | {('yourls.website', l['a']) for l in LINKS if l['s'] == 'yourls.website_wayback'}
WIKI_DERIVED = ('tinyurl.com', 'is.gd', 'v.gd', 'da.gd', 'ctxr.me', '2dd.pl', 'bitily.in')
_wd = collections.defaultdict(list)
if os.path.exists('raw_artifacts/shorteners/resolved_shortlinks.json'):
    for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json')):
        h, a = r['host'], r['alias']
        if h not in WIKI_DERIVED or akey(h, a) in _have or a in ('http:', 'https:'): continue
        api = r.get('api') or {}; loc = r.get('location') or ''
        if not loc and h in ('is.gd', 'v.gd') and api.get('status') == 200:
            try: loc = json.loads(api['body']).get('url', '')
            except Exception: pass
        if not loc and h == 'da.gd' and api.get('status') == 200: loc = api['body'].strip()
        if 'redirect.viglink.com' in loc:
            from urllib.parse import parse_qs
            loc = parse_qs(urlsplit(loc).query).get('u', [loc])[0]
        if h == 'bitily.in' and re.fullmatch(r'https?://bitily\.in/(MYLABI/?|admin/?)?', loc or ''): loc = ''  # wiped: blank redirect
        m = _first_mention.get(akey(h, a)); ch = _vd_chain.get((h, a))
        if m:
            t = m['time'].replace('T', ' ').rstrip('Z'); ip = (m['ip16'] + '.0.0/16') if m['ip16'] else ''; og = origin16(m['ip16']); ap = 'wiki'
        elif ch:
            t = ch['t']; ip = ch['ip']; og = (ch['cl'], ch['rg'], ch['an']); ap = 'chain'
        else: continue
        row = dict(s=h, a=a, t=t, ip=ip, c=0, nc=1, h=host_of(loc) if loc else '', u=(loc or '')[:600], ti=_cite_note(m) if m else '', cl=og[0], rg=og[1], an=og[2], su=r['short_url'], ap=ap, st=r.get('status'))
        if ch and m: row['ch'] = dict(a=ch['a'], t=ch['t'], ip=ch['ip'])
        wb = wb_of(r['short_url'])
        if wb: row['wb'] = wb
        LINKS.append(row); _wd[h].append(row); _have.add(akey(h, a))
# every wiki-cited short link that still has no row (ctxr.me whole-URL probes, deleted vanderbi.lt keywords) becomes a
# wiki-derived row built from the citation alone, so the Links table covers 100% of the DB's short links
_st = {(r['host'], r['alias']): r for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json'))} if os.path.exists('raw_artifacts/shorteners/resolved_shortlinks.json') else {}
for k, m in sorted(_first_mention.items(), key=lambda kv: kv[1]['time']):
    h, a = k
    if not a or k in _have or a.endswith('.php') or h.startswith('yourls.'): continue
    su = f'https://{h}/{a}'; og = origin16(m['ip16'])
    rs = _st.get((h, a)) or (_st.get((h, 'https:')) if h == 'ctxr.me' and a.startswith('https:') else _st.get((h, 'http:')) if h == 'ctxr.me' else None) or {}
    u = ''
    if h == 'ctxr.me': u = a  # the "alias" is the URL the agent asked ctxr.me to summarise
    row = dict(s=h, a=a, t=m['time'].replace('T', ' ').rstrip('Z'), ip=(m['ip16'] + '.0.0/16') if m['ip16'] else '', c=0, nc=1, h=host_of(u) if u else '', u=u[:600], ti=_cite_note(m), cl=og[0], rg=og[1], an=og[2], su=su, ap='wiki', st=rs.get('status'))
    wb = wb_of(su)
    if wb: row['wb'] = wb
    LINKS.append(row); _wd[h].append(row); _have.add(k)
for h, rows in sorted(_wd.items()):
    if any(sv['id'] == h for sv in SERVICES):  # e.g. a deleted vanderbi.lt keyword: the row joins the live service, no second entry
        for d_, n in collections.Counter(r['t'][:10] for r in rows).items(): DAILY[h][d_] = DAILY[h].get(d_, 0) + n
        continue
    DAILY[h] = dict(sorted(collections.Counter(r['t'][:10] for r in rows).items()))
    nwiki = sum(1 for r in rows if r['ap'] == 'wiki')
    SERVICES.append(dict(id=h, kind='wiki-derived (no listing API)', api='db_extracts/shortlink_mentions.json + raw_artifacts/shorteners/resolved_shortlinks.json' + (' + raw_artifacts/shorteners/da.gd/stats.json' if h == 'da.gd' else ''),
                         user_agent='(no listing fetched; per-alias resolution with the research UA)', fetched_at=None, stats=None, server_tz=None,
                         tz_note='time = first wiki citation (UTC) for %d rows, vanderbi.lt chain creation (UTC) for %d rows; creation time is not exposed by this service' % (nwiki, len(rows) - nwiki),
                         n_fetched=len(rows), n_window=len(rows), oldest=min(r['t'] for r in rows), newest=max(r['t'] for r in rows),
                         raw_files=['raw_artifacts/shorteners/resolved_shortlinks.json', 'db_extracts/shortlink_mentions.json'] + (['raw_artifacts/shorteners/da.gd/stats.json'] if h == 'da.gd' else []) + (['raw_artifacts/shorteners/wayback_aliases.json'] if WB else [])))
print('wiki-derived rows:', {h: len(r) for h, r in _wd.items()})
# --- pre-existing links the swarm REUSED (not agent-created): vanderbi.lt (tools/find_reused_links.py) and the probe targets on other
# university shorteners (tools/parse_probe_targets.py). Their creation dates are years before the window, so t = first agent-era click
# day (server-local), ct = real creation, c = in-window clicks (lower bound: sampled all-time chart), lc = lifetime clicks, ap='reused'.
# They are excluded from creator-IP counts and from the hour/weekday panels (no creation time inside the window).
_RE = 'raw_artifacts/shorteners/vanderbi.lt/reused_links.json'; _PT = 'raw_artifacts/shorteners/probe_targets.json'; _reused = []
if os.path.exists(_RE):
    for r in json.load(open(_RE))['links']:
        try: og = origin(r['creator_ip']) if r.get('creator_ip') else ('other', '', '')
        except Exception: og = ('other', '', '')
        _reused.append(dict(s='vanderbi.lt', a=r['alias'], t=r['first_agent_day'] + ' 00:00:00', ct=to_utc(r['created'], 'America/Chicago'), ip=r.get('creator_ip') or '', c=r['inwindow_clicks'], lc=r['lifetime_clicks'],
                            h=host_of(r['target']), u=r['target'][:600], ti=(r['title'] or '')[:200] if r['title'] != r['target'] else '', cl=og[0], rg=og[1], an=og[2], su=r['short_url'], ap='reused', ev=r['evidence'], pk=r['peak']))
if os.path.exists(_PT):
    for r in json.load(open(_PT))['links']:
        if not r['inwindow_hits']: continue
        row = dict(s=r['host'], a=r['alias'], t=r['first_agent_day'] + ' 00:00:00', ct=r['created'], ip='', c=r['inwindow_hits'], lc=r['lifetime_hits'], h=host_of(r['target']), u=r['target'][:600], ti='', cl='other', rg='', an='',
                   su=r['short_url'], ap='reused', ev=r['why'], pk=r['peak'], cd=[[d, h] for d, h in r['days_inwindow']], rc=r['referrer_urls_total'], rn=r['referrer_urls_n'], rh=[[h, c] for h, c in r['referrer_hosts'][:40]], rf=r['referrer_urls_top'])
        if r['sampled']: row['cds'] = 1
        _reused.append(row)
        if not any(sv['id'] == r['host'] for sv in SERVICES):
            SERVICES.append(dict(id=r['host'], kind='YOURLS (read API locked; pre-existing links reused by the swarm as reachability probes)', api='https://%s/<alias>+ (public stats page, read-only)' % r['host'],
                                 user_agent='CollusionWikiResearch/1.0 (URL-shortener abuse research)', fetched_at=r['page_fetched'], stats=None, server_tz=None,
                                 tz_note='creation date as printed by the stats page (server local); row time = first agent-era click day', n_fetched=0, n_window=0, oldest=r['created'], newest=r['created'],
                                 raw_files=['raw_artifacts/shorteners/probe_targets.json', 'tools/parse_probe_targets.py']))
            DAILY.setdefault(r['host'], {})
        sv = next(sv for sv in SERVICES if sv['id'] == r['host']); sv['raw_files'] = sorted(set(sv['raw_files']) | {r['page']})
LINKS.extend(_reused); print('pre-existing links reused by the swarm:', len(_reused), collections.Counter(l['s'] for l in _reused))
# --- topics (rough task families; tools/topics.py) ---
_alias_url = {(l['s'], l['a'].lower()): l['u'] for l in LINKS}
if os.path.exists('raw_artifacts/shorteners/resolved_shortlinks.json'):  # aliases known only from resolution (e.g. the da.gd hops inside Referer chains)
    for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json')):
        api = r.get('api') or {}; loc = r.get('location') or ''
        if not loc and r['host'] in ('is.gd', 'v.gd') and api.get('status') == 200:
            try: loc = json.loads(api['body']).get('url', '')
            except Exception: pass
        if not loc and r['host'] == 'da.gd' and api.get('status') == 200: loc = api['body'].strip()
        if not loc and r['host'] == 'tinyurl.com' and api.get('location'): loc = api['location']
        if loc and loc.startswith('http'): _alias_url.setdefault((r['host'], r['alias'].lower()), loc)
def _resolve(host, alias):
    for h in (host, host.replace('www.', '')):
        u = _alias_url.get((h, alias.lower().rstrip('+')))  # ALIAS+ is the YOURLS stats page of ALIAS
        if u: return u
    return None
from topics import leaf, chain
LEAF_LOST = {'chain-lost': '(chain: target unrecoverable)', 'proxy-lost': '(proxy call: no inner URL)', 'none': '(no target)'}
for l in LINKS:
    l['tp'], l['tk'] = classify(l['u'], l['a'], l['ti'], l['ip'], _resolve, service=l['s'])
    lh, ld, st = leaf(l['u'], _resolve)
    l['lh'] = lh if st == 'ok' else LEAF_LOST[st]; l['ld'] = ld  # leaf (innermost) target host and nesting depth
    if ld or st != 'ok': l['tc'] = chain(l['u'], _resolve)  # full target-side chain (omitted for plain links: [['final', h]])
print('leaf hosts:', collections.Counter(l['lh'] for l in LINKS).most_common(8), '· nested:', sum(1 for l in LINKS if l['ld']), '· lost:', sum(1 for l in LINKS if l['lh'].startswith('(')))
TOPICS = {}
for l in LINKS:
    t = TOPICS.setdefault(l['tp'], dict(topic=l['tp'], kind=l['tk'], n=0, ips=set(), first=l['t'], last=l['t'], hosts=collections.Counter(), aliases=[], services=collections.Counter(), clicks=0))
    t['n'] += 1; (t['ips'].add(l['ip']) if l.get('ap') != 'wiki' else None); t['first'] = min(t['first'], l['t']); t['last'] = max(t['last'], l['t']); t['hosts'][l['h']] += 1; t['services'][l['s']] += 1; t['clicks'] += l['c']
    if len(t['aliases']) < 6 and not re.fullmatch(r'[0-9a-z]{5}', l['a']): t['aliases'].append(l['a'])
TOPICS = [dict(topic=t['topic'], kind=t['kind'], n=t['n'], ips=len(t['ips']), first=t['first'][:10], last=t['last'][:10], hosts=[h for h, _ in t['hosts'].most_common(4)], aliases=t['aliases'], services=dict(t['services']), clicks=t['clicks']) for t in sorted(TOPICS.values(), key=lambda t: -t['n'])]
# DB mentions
mentions = json.load(open('db_extracts/shortlink_mentions.json'))
by_alias = collections.defaultdict(list)
for i, m in enumerate(mentions):
    by_alias[akey(m['host'], m['alias'], m['url'])].append(i)
for l in LINKS:
    idx = by_alias.get(akey(l['s'], l['a'])) or (by_alias.get(('bitily.in', 'MYLABI/' + l['a'])) if l['s'] == 'bitily.in_wayback' else None)
    if idx: l['w'] = idx
# --- potential wiki mentions: revisions that cite the link's *target* URL directly, without the short link
# (tools/extract_wiki_url_citations.py reads the built link list, so the pipeline is build -> extract -> build) ---
WCITES = json.load(open('db_extracts/wiki_url_citations.json')) if os.path.exists('db_extracts/wiki_url_citations.json') else {}
if WCITES:
    def _endpoint(u):
        try: s = urlsplit(u)
        except Exception: return ''
        h = s.netloc.lower(); h = h[4:] if h.startswith('www.') else h
        return h + s.path.rstrip('/')
    for l in LINKS:
        e = _endpoint(l['u']); x = WCITES['exact'].get(l['u']); p = WCITES['endpoint'].get(e); hn = WCITES['hosts'].get(l['h'])
        if x: l['wx'] = x['n']          # revisions citing the target URL verbatim
        if p: l['we'] = p['n']; l['wk'] = e   # revisions citing the same endpoint (ignoring query etc.); key into WCITES['endpoint']
        if hn: l['wh'] = hn             # revisions citing anything on the target host
# --- per-link referrer data (vanderbi.lt + stats pages; tools/harvest_referrers.py) ---
# rc/rn = TRUE totals over all referring URLs; rh = per-host totals (accurate, compact);
# rf = top-60 full URLs kept only as a drill-down sample (some links have thousands).
REFPS = sorted(glob.glob('raw_artifacts/shorteners/*/referrers/referrers.jsonl'))
if REFPS:
    refby = {}
    for refp in REFPS:
        rsid = refp.split('/')[2]
        for line in open(refp):
            try: rec = json.loads(line)
            except Exception: continue
            if rec.get('error') or not rec.get('urls'): continue
            refby[(rsid, rec['alias'])] = rec['urls']
    n_ref = 0
    for l in LINKS:
        u = refby.get((l['s'], l['a']))
        if not u: continue
        n_ref += 1
        hc = collections.Counter()
        for it in u: hc[host_of(it['url'])] += it['count']
        l['rc'] = sum(it['count'] for it in u)
        l['rn'] = len(u)
        l['rh'] = [[h, c] for h, c in hc.most_common(40)]
        items = sorted(u, key=lambda x: x.get('count', 0), reverse=True)[:60]
        l['rf'] = [[host_of(it['url']), it['url'][:300], it['count']] for it in items]
        # referrer-side hop histogram: how many wrappers (proxy / short link / wayback) the referring URL itself contains
        rd = collections.Counter(); routes = collections.Counter()
        for it in u:
            ch = chain(it['url'], _resolve); rd[len(ch) - 1] += it['count']
            routes[json.dumps(ch, separators=(',', ':'))] += it['count']
        l['rdh'] = sorted(rd.items())
        top = routes.most_common(40); rest = sum(routes.values()) - sum(n for _, n in top)
        l['rr'] = [[json.loads(k), n] for k, n in top] + ([[[['other', '(other referrers)']], rest]] if rest else [])  # referrer-side routes, top 40 per link
    print('links with referrer data:', n_ref)
# --- per-link click-date series (actual click days, not creation days) ---
# vanderbi.lt: tools/extract_click_series.py parses the hits-per-day charts of every harvested `+` page. YOURLS samples the
# all-time chart to <=30 points (older links lose every Nth day), the 30-day chart is complete; dates are server-local days.
# da.gd: the /stats/ALIAS page's trailing-60-day series (tools/fetch_dagd_stats.py).
CSP = 'raw_artifacts/shorteners/vanderbi.lt/referrers/click_series.json'
CLICK_META = {}
if os.path.exists(CSP):
    cs = json.load(open(CSP)); n_cs = 0; n_samp = 0
    for l in LINKS:
        if l['s'] != 'vanderbi.lt': continue
        r = cs.get(l['a'])
        if not r: continue
        l['cd'] = [[d, h] for d, h in r['days'] if h]; n_cs += 1; n_samp += bool(r.get('sampled'))
        if r.get('sampled'): l['cds'] = 1
        if r.get('hours'): l['hh'] = sorted([int(h), v] for h, v in r['hours'].items())
    CLICK_META['vanderbi.lt'] = dict(links=n_cs, sampled=n_samp, complete_from=min((r['complete_from'] for r in cs.values() if r.get('complete_from')), default=None), harvest_day=(lambda ms: time.strftime('%Y-%m-%d', time.gmtime(max(ms))) if ms else None)([os.path.getmtime(p) for p in glob.glob('raw_artifacts/shorteners/vanderbi.lt/referrers/raw/*.html.gz')]), hours_links=sum(1 for l in LINKS if l.get('hh')), note='server-local days (America/Chicago); all-time chart sampled to <=30 points per link (older links lose every Nth day), complete daily values from the 30-day chart')
    print('links with click-date series:', n_cs, 'of which sampled:', n_samp)
if DAGD:
    n = 0
    for l in LINKS:
        if l['s'] == 'da.gd' and DAGD['aliases'].get(l['a'], {}).get('days'):
            l['cd'] = [[d, h] for d, h in DAGD['aliases'][l['a']]['days'] if h]; n += 1
    CLICK_META['da.gd'] = dict(links=n, complete_from=DAGD['aliases'][next(a for a in DAGD['aliases'] if DAGD['aliases'][a].get('days'))]['span'][0], note='trailing 60 days only (stats page), complete daily values; timezone as served')
# --- wiki activity per day (all revisions in the dump, not just shortener citations) ---
WIKI_DAILY = {}
if os.path.exists('collusion-wiki.db'):
    import sqlite3
    con = sqlite3.connect('collusion-wiki.db')
    for d_, n, pg, lb in con.execute("select substr(time,1,10), count(*), count(distinct page_key), count(distinct label) from revisions group by 1 order by 1"):
        WIKI_DAILY[d_] = dict(rev=n, pages=pg, labels=lb)
    json.dump(WIKI_DAILY, open('db_extracts/wiki_daily.json', 'w'), indent=0)
elif os.path.exists('db_extracts/wiki_daily.json'):
    WIKI_DAILY = json.load(open('db_extracts/wiki_daily.json'))
# resolved short links (other services)
resolved = []
if os.path.exists('raw_artifacts/shorteners/resolved_shortlinks.json'):
    for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json')):
        api = r.get('api') or {}
        loc = r.get('location') or ''
        if not loc and r['host'] in ('is.gd', 'v.gd') and api.get('status') == 200:
            try: loc = json.loads(api['body']).get('url', '')
            except Exception: pass
        if not loc and r['host'] == 'da.gd' and api.get('status') == 200: loc = api['body'].strip()
        via = ''
        if 'redirect.viglink.com' in loc:
            from urllib.parse import parse_qs
            u = parse_qs(urlsplit(loc).query).get('u', [''])[0]
            if u: via = 'viglink'; loc = u
        if r['host'] in ('is.gd', 'v.gd') and r.get('status') == 200 and loc: via = 'preview page'
        if r.get('probe') == 'api-only': via = 'api only'
        resolved.append(dict(s=r['host'], a=r['alias'], su=r['short_url'], st=r.get('status') or (api.get('status') if r.get('probe') == 'api-only' else None), loc=loc[:600], h=host_of(loc) if loc else '', src=r['sources'],
                             labels=r['labels'], first=r['first_seen'], via=via, api=api.get('status'), stats=(r.get('stats_page') or {}).get('has_stats'), err=(r.get('error') or '')[:120], wb=wb_of(r['short_url']),
                             dg=(DAGD['aliases'].get(r['alias'], {}).get('total') if DAGD and r['host'] == 'da.gd' else None)))
probes = {}
if os.path.exists('raw_artifacts/shorteners/probes.json'):
    for b, rec in json.load(open('raw_artifacts/shorteners/probes.json')).items():
        if b.startswith('_') or not all(isinstance(v, dict) for v in rec.values()): continue  # free-text notes added later
        probes[b] = {k: (v.get('status') if 'status' in v else 'ERR ' + v.get('error', '')[:50]) for k, v in rec.items()}
        st = rec.get('stats', {})
        if isinstance(st.get('json'), dict): probes[b]['stats_json'] = st['json'].get('stats')
data = dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), window_start=WINDOW_START, services=SERVICES, links=LINKS, daily=DAILY,
            mentions=mentions, wcites=WCITES, resolved=resolved, probes=probes, origin_meta=ORIGIN.get('meta', {}), topics=TOPICS,
            dagd=(dict(fetched_at=DAGD['fetched_at'], api=DAGD['api'], note=DAGD['note'], aliases={a: dict(total=d.get('total'), span=d.get('span'), status=d.get('status')) for a, d in DAGD['aliases'].items()}) if DAGD else None), click_meta=CLICK_META, wiki_daily=WIKI_DAILY,
            wayback=(dict(fetched_at=WB.get('fetched_at'), api=WB['api'], n=len(WB['links'])) if WB else None),
            db=dict(path='./collusion-wiki.db', n_mentions=len(mentions), n_distinct=len([k for k in by_alias if k[1] and not k[1].endswith('.php')]),
                    distinct_by_host={h: sum(1 for k in by_alias if k[0] == h and k[1] and not k[1].endswith('.php')) for h in {k[0] for k in by_alias}}),
            raw=dict(root=".", files=sorted(os.path.relpath(p, ROOT) for p in glob.glob('raw_artifacts/shorteners/**/*', recursive=True) if os.path.isfile(p) and '/pages/' not in p) + sorted(os.path.relpath(p, ROOT) for p in glob.glob('raw_artifacts/vanderbilt_*') + glob.glob('raw_artifacts/y_*.json') + glob.glob('db_extracts/*shortlink*') + glob.glob('db_extracts/vanderbilt_*') + glob.glob('raw_artifacts/ip_origin/*')) + sorted(os.path.relpath(p, ROOT) for p in glob.glob('subagent_reports/*.md') + ['SHORTENERS.md', 'SWEEP2.md', 'FINDINGS.md'] if os.path.exists(p)) + sorted(os.path.relpath(p, ROOT) for p in glob.glob('raw_artifacts/sweep2/*/*') if os.path.isfile(p) and not p.endswith('.html') and '/websearch/' not in p and '/cdx/' not in p) + ['tools/fetch_yourls.py', 'tools/fetch_dagd_stats.py', 'tools/extract_click_series.py', 'tools/cdx_aliases.py', 'tools/lookup_ip_origin.py', 'tools/probe_yourls_instances.py', 'tools/resolve_shortlinks.py', 'tools/extract_db_shortlinks.py', 'tools/extract_wiki_url_citations.py', 'db_extracts/wiki_url_citations.json', 'tools/topics.py', 'tools/build_dashboard.py', 'dashboard/data.json', 'dashboard/template.html']))
json.dump(data, open('dashboard/data.json', 'w'), separators=(',', ':'))
tpl = open('dashboard/template.html').read()
import gzip, base64
raw = json.dumps(data, separators=(',', ':')).encode()
b64 = base64.b64encode(gzip.compress(raw, 9)).decode()
html = tpl.replace('/*__DATA_GZ__*/""', '"' + b64 + '"')
open('dashboard/index.html', 'w').write(html)
print('links', len(LINKS), 'services', [s['id'] for s in SERVICES], 'mentions', len(mentions), 'resolved', len(resolved), 'size', len(html))
