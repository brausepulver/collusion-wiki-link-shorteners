#!/usr/bin/env python3
"""Dump a YOURLS instance's public stats API (action=stats) page by page.

Usage: fetch_yourls.py <base_url> <outdir> [--page N] [--max-pages N] [--stop-before YYYY-MM-DD]
Writes outdir/pages/page_NNNN.json (raw), outdir/links.csv (merged), outdir/meta.json.
"""
import sys, json, time, csv, os, argparse, requests
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research)'
ap = argparse.ArgumentParser()
ap.add_argument('base'); ap.add_argument('outdir')
ap.add_argument('--page', type=int, default=2000)
ap.add_argument('--max-pages', type=int, default=100)
ap.add_argument('--stop-before', default=None, help='stop once oldest timestamp on a page < this date')
ap.add_argument('--filter', default='last')
ap.add_argument('--sleep', type=float, default=1.5)
ap.add_argument('--timeout', type=float, default=90)
ap.add_argument('--start', type=int, default=0)
a = ap.parse_args()
os.makedirs(os.path.join(a.outdir, 'pages'), exist_ok=True)
s = requests.Session(); s.headers['User-Agent'] = UA
base = a.base.rstrip('/')
api = base + '/yourls-api.php'
meta = dict(base=base, api=api, user_agent=UA, fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            pages=[], stats=None, error=None)
allrows = {}
start = a.start
for i in range(a.max_pages):
    params = dict(action='stats', format='json', filter=a.filter, limit=a.page, start=start)
    t0 = time.time()
    try:
        r = s.get(api, params=params, timeout=a.timeout)
    except Exception as e:
        meta['error'] = f'page {i}: {e!r}'; print(meta['error'], file=sys.stderr); break
    rec = dict(i=i, start=start, status=r.status_code, bytes=len(r.content), secs=round(time.time()-t0, 1), url=r.url)
    meta['pages'].append(rec)
    open(os.path.join(a.outdir, 'pages', f'page_s{start}_{i:04d}.json'), 'wb').write(r.content)
    try:
        d = r.json()
    except Exception as e:
        meta['error'] = f'page {i}: non-JSON ({r.status_code}) {r.text[:200]!r}'; print(meta['error'], file=sys.stderr); break
    meta['stats'] = d.get('stats', meta['stats'])
    links = d.get('links') or {}
    if not isinstance(links, dict) or not links:
        rec['n'] = 0; print(f'page {i}: no links; stopping', file=sys.stderr); break
    rec['n'] = len(links)
    oldest = None
    for v in links.values():
        alias = v['shorturl'].split('/')[-1]
        allrows[alias] = v
        ts = v.get('timestamp', '')
        oldest = ts if oldest is None or ts < oldest else oldest
    rec['oldest'] = oldest
    print(f'page {i}: start={start} n={len(links)} oldest={oldest} total={len(allrows)} {rec["secs"]}s', file=sys.stderr)
    if len(links) < a.page: break
    if a.stop_before and oldest and oldest[:10] < a.stop_before: break
    start += a.page
    time.sleep(a.sleep)
meta['n_links'] = len(allrows)
with open(os.path.join(a.outdir, 'links.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['alias', 'timestamp', 'ip', 'clicks', 'title', 'url', 'shorturl'])
    for alias, v in sorted(allrows.items(), key=lambda kv: kv[1].get('timestamp', '')):
        w.writerow([alias, v.get('timestamp'), v.get('ip'), v.get('clicks'), v.get('title'), v.get('url'), v.get('shorturl')])
json.dump(meta, open(os.path.join(a.outdir, 'meta.json'), 'w'), indent=1)
print(json.dumps({k: meta[k] for k in ('base', 'n_links', 'stats', 'error')}))
