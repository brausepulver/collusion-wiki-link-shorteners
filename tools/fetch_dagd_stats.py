#!/usr/bin/env python3
"""da.gd exposes a public per-alias stats page (/stats/ALIAS, HTML) with a 60-day daily access series.
Fetch it for every da.gd alias in resolved_shortlinks.json -> raw_artifacts/shorteners/da.gd/{stats/<alias>.html, stats.json}.
Read-only: the stats page does not redirect, so it adds no accesses. Incremental (aliases already in stats.json are kept; --all re-fetches). Set CONTACT=<email> to append a contact clause to the UA."""
import json, os, re, sys, time, html, requests
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research' + ('; contact ' + os.environ['CONTACT'] if os.environ.get('CONTACT') else '') + ')'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
OUT = 'raw_artifacts/shorteners/da.gd'; os.makedirs(OUT + '/stats', exist_ok=True)
s = requests.Session(); s.headers.update({'User-Agent': UA, 'Accept': 'text/html'})  # text/html: the text UA path answers "coming soon"
aliases = sorted({r['alias'] for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json')) if r['host'] == 'da.gd'})
PREV = json.load(open(OUT + '/stats.json')) if os.path.exists(OUT + '/stats.json') and '--all' not in sys.argv else None  # incremental: keep fetched aliases
res = dict(base='https://da.gd', api='https://da.gd/stats/ALIAS (HTML; Accept: text/html)', user_agent=UA.replace(os.environ.get('CONTACT', '\0'), '<contact>'),
           fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), note='daily access counts for the trailing 60 days as rendered by the stats page (uPlot data array); no creation date, creator or lifetime total is exposed', aliases={})
for a in aliases:
    if PREV and a in PREV.get('aliases', {}): res['aliases'][a] = PREV['aliases'][a]; continue
    rec = dict(alias=a)
    try:
        r = s.get(f'https://da.gd/stats/{a}', timeout=30, allow_redirects=False)
        rec['status'] = r.status_code
        open(f'{OUT}/stats/{a}.html', 'w').write(r.text)
        m = re.search(r'const data = \[\s*\[([^\]]*)\],\s*\[([^\]]*)\]', r.text, re.S)
        t = re.search(r'<title>([^<]*)</title>', r.text)
        rec['title'] = html.unescape(t.group(1)).strip() if t else ''
        if m:
            ts = [int(x) for x in m.group(1).split(',') if x.strip()]; v = [int(x) for x in m.group(2).split(',') if x.strip()]
            rec['days'] = [[time.strftime('%Y-%m-%d', time.gmtime(t_)), n] for t_, n in zip(ts, v)]
            rec['total'] = sum(v); rec['span'] = [rec['days'][0][0], rec['days'][-1][0]]
        else:
            rec['text'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style).*?</\1>', '', r.text, flags=re.S)))[:300]
    except Exception as e:
        rec['error'] = repr(e)[:200]
    res['aliases'][a] = rec
    print(a, rec.get('status'), rec.get('total'), rec.get('span'), rec.get('error', ''), file=sys.stderr)
    time.sleep(1.0)
json.dump(res, open(f'{OUT}/stats.json', 'w'), indent=1)
