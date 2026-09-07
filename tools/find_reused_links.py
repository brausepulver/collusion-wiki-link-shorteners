#!/usr/bin/env python3
"""vanderbi.lt links that were NOT created by the swarm (created before the incident window) but were used by it:
pre-window aliases whose harvested `+` page shows clicks inside the window AND either agent-tooling referrers
(jqp / allorigins / md.succ.ai / r.jina.ai / da.gd / sec.gov ...) or a spike on one of the swarm's peak days.
Inputs: links.csv (+_tail), referrers/click_series.json, referrers/referrers.jsonl (tools/harvest_referrers.py + tools/extract_click_series.py).
Output: raw_artifacts/shorteners/vanderbi.lt/reused_links.json. Coverage: every pre-window link with >=500 lifetime clicks was
harvested (plus every old alias that appears in agent referrer chains, wiki citations, agent link targets or the JD corpus),
so any pre-existing link with >=500 agent-era clicks is guaranteed to be here; smaller reuse is only found when evidence pointed at it."""
import csv, json, os, re, time, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
W0, W1 = '2026-05-01', '2026-07-31'; PEAKS = {'2026-06-18', '2026-05-27', '2026-05-28', '2026-05-29'}
AGENT_HOSTS = {'jqp.vercel.app', 'allorigins.hexlet.app', 'api.allorigins.win', 'md.succ.ai', 'markdown.new', 'r.jina.ai', 'pure.md', 'da.gd', 'is.gd', 'v.gd',
               'www.sec.gov', 'sec.gov', 'www.investor.gov', 'api.cors.lol', 'corsmirror.com', 'httpbin.org', 'api.datausa.io', 'api.dataafrica.io', 'api.microlink.io',
               'md.dhr.wtf', 'webcrawlerapi.com', 'proxy.corsfix.com', 'www.proxymule.com', 'jsonhero.io', 'api.census.gov', 'pxweb.nso.gov.vn', 'api.worldpoverty.io'}
def host_of(u):
    m = re.match(r'https?://([^/:?#]+)', u or ''); return (m.group(1) if m else '').lower()
links = {}
for f in ['raw_artifacts/shorteners/vanderbi.lt/links.csv', 'raw_artifacts/shorteners/vanderbi.lt_tail/links.csv']:
    for r in csv.DictReader(open(f)): links[r['alias']] = r
refs = {}
for line in open('raw_artifacts/shorteners/vanderbi.lt/referrers/referrers.jsonl'):
    try: r = json.loads(line)
    except Exception: continue
    if not r.get('error'): refs[r['alias']] = r
cs = json.load(open('raw_artifacts/shorteners/vanderbi.lt/referrers/click_series.json'))
harvested = {f[:-8] for f in os.listdir('raw_artifacts/shorteners/vanderbi.lt/referrers/raw')}
n_old = sum(1 for a in harvested if (links.get(a, {}).get('timestamp') or refs.get(a, {}).get('timestamp') or '') < W0)
out = []; n_inwin = 0
for a, rec in cs.items():
    lr = links.get(a) or refs.get(a) or {}
    ts = lr.get('timestamp') or ''
    if not ts or ts >= W0: continue
    inw = [[d, h] for d, h in rec['days'] if W0 <= d <= W1 and h]
    if not inw: continue
    n_inwin += 1
    urls = (refs.get(a) or {}).get('urls') or []
    ag = sum(u['count'] for u in urls if host_of(u['url']) in AGENT_HOSTS)
    agent_urls = sorted((u for u in urls if host_of(u['url']) in AGENT_HOSTS), key=lambda u: -u['count'])
    peak = max(inw, key=lambda x: x[1]); s = sum(h for _, h in inw)
    spike = peak[0] in PEAKS and peak[1] >= 5
    if not (ag >= 5 or spike): continue  # a single agent-signature referrer hit can be post-disclosure replay
    out.append(dict(alias=a, short_url=f'https://vanderbi.lt/{a}', created=ts, creator_ip=lr.get('ip') or lr.get('creator_ip') or '', target=lr.get('url') or lr.get('target') or '',
                    title=lr.get('title') or '', lifetime_clicks=int(lr.get('clicks') or 0), inwindow_clicks=s, inwindow_days=inw, peak=peak, first_agent_day=next((d for d, h in inw if h >= 5), peak[0]),
                    sampled=bool(rec.get('sampled')), agent_referrer_hits=ag, referrer_hits=sum(u['count'] for u in urls), referrer_urls=len(urls),
                    agent_referrers_top=[[host_of(u['url']), u['url'][:300], u['count']] for u in agent_urls[:40]],
                    evidence=('agent referrers' if ag else '') + (' + ' if ag and spike else '') + (f'spike on {peak[0]}' if spike else '')))
out.sort(key=lambda r: -r['inwindow_clicks'])
res = dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), window=[W0, W1], harvested_prewindow_pages=n_old, prewindow_with_inwindow_clicks=n_inwin, reused=len(out),
           rule='pre-window creation AND clicks inside the window AND (>=5 agent-tooling referrer hits OR >=5 clicks on a swarm peak day)',
           note='in-window clicks are lower bounds (all-time chart sampled to <=30 points for old links); lifetime clicks and referrer aggregates are contaminated by post-disclosure replay; timestamps server-local (America/Chicago)', links=out)
json.dump(res, open('raw_artifacts/shorteners/vanderbi.lt/reused_links.json', 'w'), indent=1)
print(f'pre-window pages harvested: {n_old}; with in-window clicks: {n_inwin}; reused by the swarm: {len(out)}')
for r in out: print(f"  {r['alias']:24s} created {r['created'][:10]} lifetime {r['lifetime_clicks']:6d} in-window {r['inwindow_clicks']:6d} peak {r['peak']} agent-ref {r['agent_referrer_hits']}/{r['referrer_hits']}  {r['evidence']}")
