#!/usr/bin/env python3
"""Pull t.mdcdev.me YOURLS stats API, merge to links.csv, filter agent_links.csv.

t.mdcdev.me is a YOURLS 1.9.2 instance with an OPEN (unauthenticated) stats API.
Stats are returned newest-first, sorted by timestamp DESC, paginated by start=.
The instance truncates the last octet of creator IPs to .0.

Usage:
  fetch_and_filter.py fetch  [--start N] [--limit N] [--pages N] [--sleep S]
  fetch_and_filter.py merge      # (re)build links.csv from pages/, write agent_links.csv, meta.json
"""
import sys, json, time, csv, os, glob, re, argparse, urllib.parse
import requests

UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research)'
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, 'pages')
BASE = 'https://t.mdcdev.me'
API = BASE + '/yourls-api.php'

# --- swarm signature (from SHORTENERS.md vanderbi.lt precedent) -------------
AGENT_HOSTS = [
    'api.dataafrica.io', 'api.worldpoverty.io', 'api.datausa.io',
    'allorigins.hexlet.app', 'md.succ.ai', 'jqp.vercel.app',
    'api.usa.gov', 'cde.ucr.cjis.gov', 'investor.gov',
    'markdown.new', 'r.jina.ai', 'httpbin.org',
    'is.gd', 'v.gd', 'da.gd',
]
# sec.gov county.json specifically (sec.gov alone is broad); handled below.
AGENT_HOST_RE = re.compile(
    r'(?:^|//|\.)(?:' + '|'.join(re.escape(h) for h in AGENT_HOSTS) + r')(?:[:/]|$)', re.I)
SEC_COUNTY_RE = re.compile(r'sec\.gov/files/county\.json', re.I)
EXAMPLE_RE = re.compile(r'//(?:www\.)?example\.(?:com|org)(?:[:/]|$)', re.I)
YOURLS_CHAIN_RE = re.compile(r'yourls-api\.php\?action=shorturl', re.I)

AGENT_KW_RE = re.compile(
    r'^(?:mass|agent|oai|openai|rw|rwanda|ma.*county|sec|county|fresh|.*json)', re.I)

# Azure AS8075 first-octet families used by the swarm (last octet truncated here)
AZURE_PREFIXES = ('20.', '4.', '40.', '52.', '104.', '13.', '172.', '137.', '65.52.')


def is_agent(v):
    url = v.get('url') or ''
    alias = (v.get('shorturl') or '').rstrip('/').split('/')[-1]
    reasons = []
    if AGENT_HOST_RE.search(url):
        reasons.append('host')
    if SEC_COUNTY_RE.search(url):
        reasons.append('sec-county')
    if EXAMPLE_RE.search(url):
        reasons.append('example')
    if YOURLS_CHAIN_RE.search(url):
        reasons.append('yourls-chain')
    return reasons, alias


def target_host(url):
    try:
        return urllib.parse.urlsplit(url).hostname or ''
    except Exception:
        return ''


POISON = []  # single-row offsets whose row breaks json_encode (invalid UTF-8 spam)


def _get(s, start, limit, timeout):
    """Return parsed JSON dict, or None if the server returned an empty body
    (a 'poison' UTF-8 row is inside [start,start+limit))."""
    r = s.get(API, params=dict(action='stats', format='json', filter='last',
                               limit=limit, start=start), timeout=timeout)
    if not r.content.strip():
        return None
    return r.json()


def _fetch_window(s, start, limit, timeout, sleep, depth=0):
    """Adaptively fetch [start, start+limit); bisect around poison rows.
    Writes each successfully-encoded sub-window to its own page file."""
    d = _get(s, start, limit, timeout)
    time.sleep(sleep)
    if d is not None:
        links = d.get('links') or {}
        n = len(links) if isinstance(links, dict) else 0
        out = os.path.join(PAGES, f'page_s{start:06d}_l{limit}.json')
        json.dump(d, open(out, 'w'))
        ts = [v['timestamp'] for v in links.values()] if n else []
        print(f'{"  "*depth}[ok] start={start} limit={limit} n={n} '
              f'newest={max(ts) if ts else "-"} oldest={min(ts) if ts else "-"}', file=sys.stderr)
        return n, (min(ts) if ts else None)
    # empty body -> poison row inside this window
    if limit == 1:
        POISON.append(start)
        print(f'{"  "*depth}[poison] offset {start} (row skipped)', file=sys.stderr)
        return 0, None
    half = limit // 2
    print(f'{"  "*depth}[split] start={start} limit={limit} -> {half}+{limit-half}', file=sys.stderr)
    n1, o1 = _fetch_window(s, start, half, timeout, sleep, depth+1)
    n2, o2 = _fetch_window(s, start + half, limit - half, timeout, sleep, depth+1)
    olds = [o for o in (o1, o2) if o]
    return n1 + n2, (min(olds) if olds else None)


def cmd_fetch(a):
    os.makedirs(PAGES, exist_ok=True)
    s = requests.Session(); s.headers['User-Agent'] = UA
    start = a.start
    total = 0
    for i in range(a.pages):
        n, oldest = _fetch_window(s, start, a.limit, a.timeout, a.sleep)
        total += n
        print(f'== window {i}: start={start} rows={n} oldest={oldest} cum={total} '
              f'poison={len(POISON)} ==', file=sys.stderr)
        if a.stop_before and oldest and oldest[:10] < a.stop_before:
            print(f'reached {oldest} < {a.stop_before}; stop', file=sys.stderr); break
        start += a.limit
    print(f'DONE total_rows={total} poison_offsets={POISON}', file=sys.stderr)


import socket
# Strict incident window (matches vanderbi.lt agent era; creation-time attribution)
WIN_LO, WIN_HI = '2026-05-12 00:00:00', '2026-07-11 23:59:59'


def cymru_asn(ips):
    """Team Cymru bulk whois -> {ip: (asn, name)}. Best-effort."""
    ips = [ip for ip in ips if ip and ':' not in ip]
    if not ips:
        return {}
    payload = 'begin\nverbose\n' + '\n'.join(sorted(set(ips))) + '\nend\n'
    out = {}
    try:
        s = socket.create_connection(('whois.cymru.com', 43), timeout=60)
        s.sendall(payload.encode()); buf = b''
        while True:
            b = s.recv(65536)
            if not b:
                break
            buf += b
        s.close()
        for line in buf.decode('utf-8', 'replace').splitlines():
            p = [x.strip() for x in line.split('|')]
            if len(p) >= 7 and p[1].count('.') == 3:
                out[p[1]] = (p[0], p[6])
    except Exception as e:
        print(f'cymru lookup failed: {e!r}', file=sys.stderr)
    return out


def cmd_merge(a):
    rows = {}
    for p in sorted(glob.glob(os.path.join(PAGES, 'page_*.json'))):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        for v in (d.get('links') or {}).values():
            alias = (v.get('shorturl') or '').rstrip('/').split('/')[-1]
            rows[alias] = v
    # links.csv
    with open(os.path.join(HERE, 'links.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['alias', 'timestamp', 'ip', 'clicks', 'title', 'url', 'shorturl'])
        for alias, v in sorted(rows.items(), key=lambda kv: kv[1].get('timestamp', '')):
            w.writerow([alias, v.get('timestamp'), v.get('ip'), v.get('clicks'),
                        v.get('title'), v.get('url'), v.get('shorturl')])
    # agent_links.csv
    agents = []
    for alias, v in rows.items():
        reasons, _ = is_agent(v)
        if reasons:
            agents.append((alias, v, reasons))
    agents.sort(key=lambda t: t[1].get('timestamp', ''))
    asn = cymru_asn([v.get('ip') for _, v, _ in agents])
    # NOTE: 'clicks_lifetime' is the YOURLS cumulative counter = CONTAMINATED
    # (lifetime total, no per-event timestamp; folds in post-disclosure researcher
    # replays from ~2026-07 on). Attribution is by creation_ts + creator_ip + target,
    # never by this column. in_window = created within the incident window.
    n_in = 0
    with open(os.path.join(HERE, 'agent_links.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['alias', 'timestamp', 'in_window', 'ip', 'ip_asn', 'ip_org',
                    'clicks_lifetime_contaminated', 'target_host', 'reasons', 'url', 'shorturl'])
        for alias, v, reasons in agents:
            ts = v.get('timestamp') or ''
            inw = WIN_LO <= ts <= WIN_HI
            n_in += inw
            ip = v.get('ip') or ''
            asn_no, asn_org = asn.get(ip, ('', 'MICROSOFT-IPv6' if ':' in ip else ''))
            w.writerow([alias, ts, inw, ip, asn_no, asn_org, v.get('clicks'),
                        target_host(v.get('url') or ''), '|'.join(reasons),
                        v.get('url'), v.get('shorturl')])
    print(f'agent links in strict window {WIN_LO[:10]}..{WIN_HI[:10]}: {n_in}/{len(agents)}', file=sys.stderr)
    # meta.json
    db = None
    s = requests.Session(); s.headers['User-Agent'] = UA
    try:
        db = s.get(API, params=dict(action='db-stats', format='json'), timeout=30).json().get('db-stats')
    except Exception as e:
        db = {'error': repr(e)}
    n_in = sum(1 for _, v, _ in agents if WIN_LO <= (v.get('timestamp') or '') <= WIN_HI)
    meta = dict(base=BASE, api=API, user_agent=UA,
                fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                pages_fetched=len(glob.glob(os.path.join(PAGES, 'page_*.json'))),
                rows_merged=len(rows), agent_links=len(agents),
                agent_links_in_window=n_in, incident_window=[WIN_LO, WIN_HI],
                rows_window_covered='2026-08-28 .. 2026-04-09 (start 0..9498)',
                db_stats=db,
                clicks_caveat='The clicks_lifetime column and all referrer aggregates are '
                              'CONTAMINATED: YOURLS lifetime counters / referrer tallies with no '
                              'per-event timestamp, folding in post-disclosure (2026-07+) researcher '
                              'replays. Attribute ONLY by creation timestamp + creator IP (Azure '
                              'AS8075) + target-URL signature. The only clean over-time signal is the '
                              'per-day binned chart in stats/per_day_series.json, sliced to <=2026-07.',
                note='YOURLS 1.9.2 open stats API; newest-first, sorted timestamp DESC; creator IP '
                     'last octet truncated to .0. Timestamps are server-local (timezone unknown). '
                     'A poison row at offset ~1105 breaks json_encode for any window covering it; '
                     'fetch bisects around it (2 poison rows skipped, both Aug spam).')
    json.dump(meta, open(os.path.join(HERE, 'meta.json'), 'w'), indent=1)
    print(json.dumps(dict(rows=len(rows), agent_links=len(agents), db=db), indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--start', type=int, default=0)
    f.add_argument('--limit', type=int, default=1000)
    f.add_argument('--pages', type=int, default=20)
    f.add_argument('--sleep', type=float, default=0.3)
    f.add_argument('--timeout', type=float, default=90)
    f.add_argument('--stop-before', default=None)
    sub.add_parser('merge')
    a = ap.parse_args()
    {'fetch': cmd_fetch, 'merge': cmd_merge}[a.cmd](a)
