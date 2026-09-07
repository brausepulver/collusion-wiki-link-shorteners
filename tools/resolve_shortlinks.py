#!/usr/bin/env python3
"""Resolve every distinct short link (from DB mentions + vanderbi.lt targets that are themselves shorteners
+ short links that appear inside the Referer chains of vanderbi.lt clicks, i.e. proxy -> da.gd/is.gd -> vanderbi.lt hops).
Records redirect target, status, and per-service metadata (is.gd forward API, da.gd coshorten).
Incremental: aliases already in resolved_shortlinks.json are kept as-is (pass --all to re-probe everything).
Referrer- and JD-sourced aliases are probed through the read-only endpoints only (no GET of the short URL, so no click is added).
Set CONTACT=<email> to append a contact clause to the UA."""
import json, csv, time, sys, os, re, requests, collections
from urllib.parse import urlsplit, quote, unquote
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research' + ('; contact ' + os.environ['CONTACT'] if os.environ.get('CONTACT') else '') + ')'
OUT = 'raw_artifacts/shorteners/resolved_shortlinks.json'
REFP = 'raw_artifacts/shorteners/vanderbi.lt/referrers/referrers.jsonl'
NOT_ALIAS = {'coshorten', 'preview', 'stats', 'help', 'ip', 'headers', 'isp', 'dns', 'host', 'ua', 'up', 'w', 's', 'edit', 'status', 'roll', 'usa', 'ec', 'forward.php', 'stats.php', 'create.php'}
s = requests.Session(); s.headers['User-Agent'] = UA
SHORT = {'tinyurl.com','is.gd','v.gd','da.gd','bitily.in','app.bitily.in','ctxr.me','2dd.pl','yourls.pro','yourls.website','short.kodact.art','vanderbi.lt'}
targets = {}
for m in json.load(open('db_extracts/shortlink_mentions.json')):
    if not m['alias']: continue
    u = m['url']
    if m['host'] == 'bitily.in':
        p = urlsplit(u).path.strip('/').split('/')
        alias = '/'.join(p[:2]) if len(p) >= 2 and p[0] == 'MYLABI' else p[0]
    else:
        alias = m['alias']
    key = (m['host'], alias)
    targets.setdefault(key, dict(host=m['host'], alias=alias, sources=set(), first_seen=m['time'], labels=set()))
    targets[key]['sources'].add('wiki-db'); targets[key]['labels'].add(m['label'])
for r in csv.DictReader(open('raw_artifacts/shorteners/vanderbi.lt/links.csv')):
    if r['timestamp'] < '2026-05-01': continue
    h = (urlsplit(r['url']).hostname or '').lower()
    if h in SHORT and h != 'vanderbi.lt':
        p = urlsplit(r['url']).path.strip('/')
        if not p or 'yourls-api' in p or 'admin' in p: continue
        alias = p.split('/')[0]
        key = (h, alias)
        targets.setdefault(key, dict(host=h, alias=alias, sources=set(), first_seen=r['timestamp'], labels=set()))
        targets[key]['sources'].add('vanderbi.lt-target')
# short links seen inside the Referer URLs of clicks on vanderbi.lt links (proxy -> da.gd -> vanderbi.lt chains); creation
# time of the earliest vanderbi.lt link they referred to stands in for first_seen (server-local, like links.csv)
REF_SHORT = re.compile(r'https?://(?:www\.)?(da\.gd|is\.gd|v\.gd|tinyurl\.com|bitily\.in|2dd\.pl|ctxr\.me)/([A-Za-z0-9_\-]+)')
if os.path.exists(REFP):
    for line in open(REFP):
        try: rec = json.loads(line)
        except Exception: continue
        if rec.get('error') or not rec.get('urls') or (rec.get('timestamp') or '') < '2026-05-01': continue
        for it in rec['urls']:
            u = it['url']
            for _ in range(3):
                d = unquote(u)
                if d == u: break
                u = d
            for h, a in REF_SHORT.findall(u):
                if a in NOT_ALIAS: continue
                key = (h, a)
                targets.setdefault(key, dict(host=h, alias=a, sources=set(), first_seen=rec['timestamp'], labels=set()))
                targets[key]['sources'].add('vanderbi.lt-referrer'); targets[key]['first_seen'] = min(targets[key]['first_seen'], rec['timestamp'])
# short links cited in JoshuaDavid's wiki exports that our DB snapshot lacks (wiki4d, paste sites, late probier revisions);
# see db_extracts/jd_shortlink_mentions.json. Probed read-only like the referrer-sourced ones.
JDP = 'db_extracts/jd_shortlink_mentions.json'
if os.path.exists(JDP):
    for m in json.load(open(JDP))['mentions']:
        key = (m['host'], m['alias'])
        targets.setdefault(key, dict(host=m['host'], alias=m['alias'], sources=set(), first_seen=m['time'] or '', labels=set()))
        targets[key]['sources'].add('jd-wiki'); targets[key]['labels'].add(m['label'])
        if m['time'] and (not targets[key]['first_seen'] or m['time'] < targets[key]['first_seen']): targets[key]['first_seen'] = m['time']
prev = {}
if os.path.exists(OUT) and '--all' not in sys.argv:
    prev = {(r['host'], r['alias']): r for r in json.load(open(OUT))}
    for k, r in prev.items():  # keep the source list current without re-probing
        if k in targets: r['sources'] = sorted(set(r['sources']) | targets[k]['sources'])
print(len(targets), 'distinct short links', collections.Counter(k[0] for k in targets), '· already resolved:', len(prev), file=sys.stderr)
out = [r for k, r in sorted(prev.items())]
for (host, alias), t in sorted(targets.items()):
    if (host, alias) in prev: continue
    rec = dict(host=host, alias=alias, sources=sorted(t['sources']), labels=sorted(t['labels']), first_seen=t['first_seen'])
    short = f'https://{host}/{alias}'
    rec['short_url'] = short
    api_only = t['sources'] <= {'vanderbi.lt-referrer', 'jd-wiki'} and host in ('is.gd', 'v.gd', 'da.gd', 'tinyurl.com')
    if api_only: rec['probe'] = 'api-only'  # read-only endpoints only: no click added to the short link
    else:
        try:
            r = s.get(short, timeout=20, allow_redirects=False)
            rec['status'] = r.status_code; rec['location'] = r.headers.get('Location'); rec['server'] = r.headers.get('Server')
            if r.status_code == 200: rec['body_head'] = r.text[:300]
        except Exception as e:
            rec['error'] = repr(e)
    try:
        if host in ('is.gd', 'v.gd'):
            r = s.get(f'https://{host}/forward.php', params=dict(format='json', shorturl=alias), timeout=20)
            rec['api'] = dict(status=r.status_code, body=r.text[:500])
            r = s.get(f'https://{host}/stats.php', params=dict(url=alias), timeout=20)
            rec['stats_page'] = dict(status=r.status_code, has_stats=('Total clicks' in r.text or 'clicks' in r.text.lower()), body=r.text[:800])
        elif host == 'da.gd':
            r = s.get(f'https://da.gd/coshorten/{alias}', timeout=20)
            rec['api'] = dict(status=r.status_code, body=r.text[:500])
        elif host == 'tinyurl.com':
            r = s.get(f'https://tinyurl.com/preview/{alias}', timeout=20, allow_redirects=False)
            rec['api'] = dict(status=r.status_code, body=r.text[:600], location=r.headers.get('Location'))
    except Exception as e:
        rec['api_error'] = repr(e)
    out.append(rec)
    print(host, alias, rec.get('status'), (rec.get('location') or '')[:80], file=sys.stderr)
    time.sleep(0.8)
out.sort(key=lambda r: (r['host'], r['alias']))
json.dump(out, open(OUT, 'w'), indent=1)
with open('raw_artifacts/shorteners/resolved_shortlinks.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['host','alias','short_url','status','location','sources','labels','first_seen','api_status','api_body'])
    for r in out:
        w.writerow([r['host'], r['alias'], r['short_url'], r.get('status'), r.get('location'), ';'.join(r['sources']), ';'.join(r['labels']), r['first_seen'], (r.get('api') or {}).get('status'), ((r.get('api') or {}).get('body') or '')[:300].replace('\n',' ')])
print('done', len(out), file=sys.stderr)
