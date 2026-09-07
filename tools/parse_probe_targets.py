#!/usr/bin/env python3
"""Pre-existing short links on OTHER shorteners that the swarm used as reachability probes (never agent-created):
parse their harvested YOURLS `<alias>+` stats pages -> raw_artifacts/shorteners/probe_targets.json.
Per alias: target, creation date (server-local, as printed), lifetime hits (contaminated), the all-time daily
series restricted to the incident window (YOURLS samples it to <=30 points, so in-window sums are lower bounds),
peak day, referrer hosts (contaminated aggregate) and the referring URLs with an agent-tooling signature.
Pages: raw_artifacts/shorteners/<host>/plus/<alias>.html (read-only fetches with the research UA)."""
import re, os, csv, json, html, glob, collections, time
from datetime import datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
W0, W1 = '2026-05-01', '2026-07-31'
# (host, alias, why it is in scope)
TARGETS = [
    ('goto.unm.edu', '7t6-o', 'UNM YOURLS example link (2023); referrer of vanderbi.lt/iyg1y; 5 goto.unm.edu bodies in the JD/shellac corpus'),
    ('goto.unm.edu', 'discvr', 'UNM library link (2019); JD/shellac corpus'),
    ('goto.unm.edu', 'reso', 'UNM sustainability link (2021); JD/shellac corpus'),
    ('goto.unm.edu', 'urphy21', 'UNM zoom link (2021); JD/shellac corpus'),
    ('uoft.me', 'utmace', 'UofT 2013 link used as the reachability example (like vanderbi.lt/iyg1y)'),
    ('u.ethz.ch', 'nB1nv', 'ETH 2020 link probed 2026-06-18; JD/shellac corpus records a nB1nv+jqpaccess probe'),
]
AGENT_HOSTS = {'jqp.vercel.app', 'allorigins.hexlet.app', 'api.allorigins.win', 'md.succ.ai', 'markdown.new', 'r.jina.ai', 'pure.md', 'da.gd', 'is.gd', 'v.gd',
               'www.sec.gov', 'sec.gov', 'www.investor.gov', 'api.cors.lol', 'corsmirror.com', 'httpbin.org', 'api.datausa.io', 'api.dataafrica.io', 'api.microlink.io',
               'md.dhr.wtf', 'webcrawlerapi.com', 'proxy.corsfix.com', 'www.proxymule.com', 'jsonhero.io', 'api.census.gov', 'pxweb.nso.gov.vn', 'docs.google.com'}
def host_of(u):
    m = re.match(r'https?://([^/:?#]+)', u or ''); return (m.group(1) if m else '').lower()
def parse(fp):
    h = open(fp, encoding='utf-8', errors='replace').read()
    d = {}
    m = re.search(r'<a href="([^"]+)" id="longurl"', h); d['target'] = html.unescape(m.group(1)) if m else ''
    m = re.search(r'Short URL created on ([^<(]+?)\s*\(about (\d+) days ago\)', h); d['created_local'] = m.group(1).strip() if m else ''
    try: d['created'] = datetime.strptime(d['created_local'].replace('@ ', ''), '%B %d, %Y %I:%M %p').strftime('%Y-%m-%d %H:%M:%S')
    except Exception: d['created'] = ''
    hist = {lbl.strip(): int(n.replace(',', '')) for lbl, n in re.findall(r"'>([^<]+)</a></span>\s*<span class='historical_count'>([\d,]+) hits", h)}
    d['lifetime_hits'] = hist.get('All time', 0); d['hits_30d_at_harvest'] = hist.get('Last 30 days', 0)
    tables = [m.group(1) for m in re.finditer(r'arrayToDataTable\((\[.*?\])\);', h, re.S)]
    dated = [re.findall(r"\['([A-Z][a-z]{2} \d\d, \d{4})',\s*(\d+)\]", body) for body in tables]
    dated = [x for x in dated if x]
    conv = lambda rows: {datetime.strptime(dd, '%b %d, %Y').strftime('%Y-%m-%d'): int(n) for dd, n in rows}
    # page order: last 7 days, last 30 days, all time; the all-time chart is the one that starts earliest (it is sampled to
    # <=30 points, so it can be SHORTER than the 30-day chart)
    conv_all = [conv(x) for x in dated]
    alltime = min(conv_all, key=lambda s: min(s)) if conv_all else {}
    d30 = next((s for s in conv_all if s is not alltime and len(s) >= 28), {})
    merged = dict(alltime); merged.update(d30)
    d['days_all'] = sorted([[k, v] for k, v in merged.items()]); d['sampled'] = len(alltime) >= 30
    inw = [[k, v] for k, v in sorted(merged.items()) if W0 <= k <= W1 and v]
    d['days_inwindow'] = inw; d['inwindow_hits'] = sum(v for _, v in inw)
    d['peak'] = max(inw, key=lambda x: x[1]) if inw else None
    # first in-window day with >=5 hits (stray single hits in May are ordinary human traffic), else the peak day
    d['first_agent_day'] = next((k for k, v in inw if v >= 5), d['peak'][0]) if inw else None
    hosts = re.findall(r"sites_list'>.*?/>\s*([^:<]+):\s*<strong>([\d,]+)</strong>", h)
    d['referrer_hosts'] = [[hh.strip(), int(c.replace(',', ''))] for hh, c in hosts]
    urls = [(html.unescape(u), int(n)) for u, n in re.findall(r"""<a href=["']([^"']*)["'][^>]*>[^<]*</a>\s*:\s*(?:<strong>)?(\d+)""", h)]
    d['referrer_urls_total'] = sum(n for _, n in urls); d['referrer_urls_n'] = len(urls)
    d['agent_referrer_hits'] = sum(n for u, n in urls if host_of(u) in AGENT_HOSTS)
    d['referrer_urls_top'] = [[host_of(u), u[:300], n] for u, n in sorted(urls, key=lambda x: -x[1])[:60]]
    return d
out = dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), window=[W0, W1],
           note='pre-existing links (not agent-created) reused by the swarm as reachability probes; in-window hits are a lower bound (sampled all-time chart); lifetime hits and referrer aggregates are contaminated by post-disclosure replay', links=[])
for host, alias, why in TARGETS:
    fp = f'raw_artifacts/shorteners/{host}/plus/{alias}.html'
    if not os.path.exists(fp): print('missing', fp); continue
    d = parse(fp); d.update(host=host, alias=alias, short_url=f'https://{host}/{alias}', why=why, page=os.path.relpath(fp, ROOT), page_fetched=time.strftime('%Y-%m-%d', time.gmtime(os.path.getmtime(fp))))
    out['links'].append(d)
    print(f"{host}/{alias}: created {d['created']} lifetime {d['lifetime_hits']} in-window {d['inwindow_hits']} peak {d['peak']} agent-ref {d['agent_referrer_hits']}/{d['referrer_urls_total']} target {d['target'][:60]}")
json.dump(out, open('raw_artifacts/shorteners/probe_targets.json', 'w'), indent=1)
