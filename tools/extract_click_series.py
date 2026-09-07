#!/usr/bin/env python3
"""Parse the 'Number of hits : All time' line chart out of every harvested vanderbi.lt `+` stats page
(raw_artifacts/shorteners/vanderbi.lt/referrers/raw/<alias>.html.gz, fetched by tools/harvest_referrers.py)
-> raw_artifacts/shorteners/vanderbi.lt/referrers/click_series.json  {alias: {"days": [[YYYY-MM-DD, hits], ...], "best": [date, hits]}}
Dates are the server's local days (America/Chicago). YOURLS bins long ranges (every 2nd day when a link is older than ~30 days)."""
import gzip, re, json, glob, os, sys
from datetime import datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
RAW = 'raw_artifacts/shorteners/vanderbi.lt/referrers/raw'
out = {}; n_empty = 0
for f in sorted(glob.glob(RAW + '/*.html.gz')):
    alias = os.path.basename(f)[:-8]
    try: t = gzip.open(f, 'rt', errors='replace').read()
    except Exception as e: print(alias, 'ERR', e, file=sys.stderr); continue
    tables = [m.group(1) for m in re.finditer(r'arrayToDataTable\((\[.*?\])\);', t, re.S)]
    dated = [re.findall(r"\['([A-Z][a-z]{2} \d\d, \d{4})',\s*(\d+)\]", body) for body in tables]
    dated = [d for d in dated if d]  # page order: last 7 days, last 30 days, all time (24h chart has hour labels)
    if not dated: n_empty += 1; continue
    conv = lambda rows: {datetime.strptime(d, '%b %d, %Y').strftime('%Y-%m-%d'): int(h) for d, h in rows}
    alltime = conv(max(dated, key=len)); d30 = conv(dated[1]) if len(dated) >= 3 else {}
    # YOURLS keeps at most 30 points on the all-time chart (every Nth day dropped for older links); the 30-day chart is
    # complete, so it overrides the all-time values inside its range
    merged = dict(alltime); merged.update(d30)
    ser = sorted([[d, h] for d, h in merged.items()])
    best = re.search(r'Best day[^<]*</h3>\s*<p>\s*<strong>([^<]*)</strong>[^<]*<strong>([^<]*)</strong>', t)
    rec = dict(days=ser, total=sum(h for _, h in ser), complete_from=min(d30) if d30 else None,
               sampled=len(alltime) >= 30 and (max(alltime) > min(alltime)))
    if best: rec['best'] = [best.group(1).strip(), best.group(2).strip()]
    # 'Last 24 hours' chart: hits per server-local hour in the 24 h before the harvest (post-incident replay traffic)
    hrs = {int(h): int(v) for body in tables for h, v in re.findall(r"\['(\d\d) [AP]M',\s*(\d+)\]", body) if int(v)}
    if hrs: rec['hours'] = hrs
    out[alias] = rec
json.dump(out, open('raw_artifacts/shorteners/vanderbi.lt/referrers/click_series.json', 'w'), separators=(',', ':'))
print(len(out), 'aliases with a click series;', n_empty, 'pages without one;', sum(r['total'] for r in out.values()), 'hits summed', file=sys.stderr)
