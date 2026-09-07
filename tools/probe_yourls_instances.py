#!/usr/bin/env python3
"""Probe candidate YOURLS instances for an open stats API. Writes raw_artifacts/shorteners/probes.json"""
import requests, json, time, sys
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research)'
BASES = ['https://2dd.pl','https://bitily.in','https://app.bitily.in','https://yourls.website','https://yourls.pro',
         'https://short.kodact.art','https://ctxr.me','http://2dd.pl','http://bitily.in','http://yourls.website','http://yourls.pro']
s = requests.Session(); s.headers['User-Agent'] = UA
out = {}
for b in BASES:
    rec = {}
    for name, url in [('root', b + '/'), ('stats', b + '/yourls-api.php?action=stats&format=json&filter=last&limit=5'),
                      ('db_stats', b + '/yourls-api.php?action=db-stats&format=json'),
                      ('admin', b + '/admin/index.php')]:
        try:
            r = s.get(url, timeout=25, allow_redirects=False)
            body = r.text[:1500]
            rec[name] = dict(status=r.status_code, location=r.headers.get('Location'), server=r.headers.get('Server'),
                             ctype=r.headers.get('Content-Type'), bytes=len(r.content), body=body)
            if name == 'stats':
                try: rec[name]['json'] = r.json()
                except Exception: pass
        except Exception as e:
            rec[name] = dict(error=repr(e))
        time.sleep(0.7)
    out[b] = rec
    print(b, {k: (v.get('status') or v.get('error', '')[:60]) for k, v in rec.items()}, file=sys.stderr)
json.dump(out, open('raw_artifacts/shorteners/probes.json', 'w'), indent=1)
