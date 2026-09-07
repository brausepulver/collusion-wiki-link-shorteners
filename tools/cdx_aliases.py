#!/usr/bin/env python3
"""Wayback CDX lookup for every short link in resolved_shortlinks.json (exact URL, http+https): when was each alias
captured, how often, with what status and (for redirects) which target the archive saw at the time.
-> raw_artifacts/shorteners/wayback_aliases.json. Read-only against archive.org; no Save Page Now. CONTACT=<email> appends a UA clause."""
import json, os, sys, time, requests
from urllib.parse import quote
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research' + ('; contact ' + os.environ['CONTACT'] if os.environ.get('CONTACT') else '') + ')'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
OUTP = 'raw_artifacts/shorteners/wayback_aliases.json'
out = json.load(open(OUTP)) if os.path.exists(OUTP) else dict(api='https://web.archive.org/cdx/search/cdx?url=<short url>&matchType=exact&output=json&fl=timestamp,statuscode,original,mimetype,digest,redirect', user_agent=UA.replace(os.environ.get('CONTACT', '\0'), '<contact>'), links={})
s = requests.Session(); s.headers['User-Agent'] = UA
todo = [r for r in json.load(open('raw_artifacts/shorteners/resolved_shortlinks.json')) if r['host'] != 'vanderbi.lt' and r['short_url'] not in out['links']]
print(len(todo), 'aliases to look up', file=sys.stderr)
fails = 0
for r in todo:
    su = r['short_url']; rec = dict(host=r['host'], alias=r['alias'], captures=[])
    try:
        q = f"https://web.archive.org/cdx/search/cdx?url={quote(su.split('://',1)[1], safe='')}&matchType=exact&output=json&fl=timestamp,statuscode,original,mimetype,digest,redirect&limit=200"
        resp = s.get(q, timeout=60)
        rec['status'] = resp.status_code
        if resp.status_code != 200 or 'Temporarily Offline' in resp.text[:400]:
            rec['error'] = resp.text[:120]; fails += 1
            if fails >= 5: print('archive.org unavailable; stopping (rerun later, progress is saved)', file=sys.stderr); break
        else:
            body = resp.text.strip(); rows = json.loads(body) if body else []
            rec['captures'] = [dict(zip(rows[0], x)) for x in rows[1:]] if rows else []
            rec['n'] = len(rec['captures']); fails = 0
            if rec['n']: rec['first'] = rec['captures'][0]['timestamp']; rec['last'] = rec['captures'][-1]['timestamp']
            out['links'][su] = rec
    except Exception as e:
        rec['error'] = repr(e)[:200]; fails += 1
    print(su, rec.get('status'), rec.get('n'), rec.get('first', ''), rec.get('error', '')[:60], file=sys.stderr)
    out['fetched_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    json.dump(out, open(OUTP, 'w'), indent=1)
    time.sleep(3.0)
print('done:', len(out['links']), 'of', len(out['links']) + len(todo) - sum(1 for r in todo if r['short_url'] in out['links']), file=sys.stderr)
