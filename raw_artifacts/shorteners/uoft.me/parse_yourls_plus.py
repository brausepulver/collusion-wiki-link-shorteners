#!/usr/bin/env python3
"""Parse YOURLS `<alias>+` stats pages (uoft.me, u.ethz.ch) harvested read-only.
Extracts: long URL (target), created date, lifetime hits, the 'all-time' downsampled
per-point series (with best point), and the referrer-host shares + top referrer URLs.
Usage: parse_yourls_plus.py <host_dir> ...  (each dir has plus/*.html)
Writes <host_dir>/aliases.csv and prints a summary.
"""
import sys, re, os, csv, json, html

def parse(fp):
    h = open(fp, encoding='utf-8', errors='replace').read()
    d = {}
    m = re.search(r'<a href="([^"]+)" id="longurl"', h)
    d['target'] = html.unescape(m.group(1)) if m else ''
    m = re.search(r'Short URL created on ([^<(]+?)\s*\(about (\d+) days ago\)', h)
    d['created'] = m.group(1).strip() if m else ''
    # historical counts
    hist = dict((lbl.strip(), int(n.replace(',', ''))) for lbl, n in
                re.findall(r"'>([^<]+)</a></span>\s*<span class='historical_count'>([\d,]+) hits", h))
    d['lifetime_hits'] = hist.get('All time', 0)
    d['hits_24h'] = hist.get('Last 24 hours', 0)
    d['hits_7d'] = hist.get('Last 7 days', 0)
    d['hits_30d'] = hist.get('Last 30 days', 0)
    # all-time downsampled series -> best point
    m = re.search(r"function yourls_graphstat_line_all.*?arrayToDataTable\((\[.*?\])\)", h, re.S)
    best = ('', 0.0); npts = 0
    if m:
        pts = [(l, float(n)) for l, n in re.findall(r"\[\s*'([^']*)'\s*,\s*([\d.]+)\s*\]", m.group(1)) if l.lower() != 'date' and l != 'Time']
        npts = len(pts)
        if pts:
            best = max(pts, key=lambda x: x[1])
    d['best_point_label'] = best[0]; d['best_point_hits'] = int(best[1]); d['series_points'] = npts
    # referrer shares pie
    m = re.search(r"yourls_graphstat_tab_source_ref.*?arrayToDataTable\((\[.*?\])\)", h, re.S)
    refs = []
    if m:
        for lbl, n in re.findall(r"\['([^']+)',\s*([\d]+)\]", m.group(1)):
            if lbl not in ('Country', 'Value'):
                refs.append((lbl, int(n)))
    d['referrer_shares'] = refs
    # exact referrer host counts from the <li class='sites_list'> list
    hosts = re.findall(r"sites_list'>.*?/>\s*([^:<]+):\s*<strong>([\d,]+)</strong>", h)
    d['referrer_hosts'] = [(hh.strip(), int(c.replace(',', ''))) for hh, c in hosts]
    return d

for hostdir in sys.argv[1:]:
    pdir = os.path.join(hostdir, 'plus')
    if not os.path.isdir(pdir):
        continue
    rows = []
    print(f"\n===== {hostdir} =====")
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith('.html'):
            continue
        fp = os.path.join(pdir, fn)
        if os.path.getsize(fp) < 500:
            continue
        alias = fn[:-5]
        d = parse(fp)
        d['alias'] = alias
        rows.append(d)
        print(f"\n[{alias}] lifetime={d['lifetime_hits']} 24h={d['hits_24h']} 7d={d['hits_7d']} 30d={d['hits_30d']}")
        print(f"  created: {d['created']}")
        print(f"  target : {d['target'][:140]}")
        print(f"  best all-time point: {d['best_point_label']} = {d['best_point_hits']} ({d['series_points']} pts)")
        print(f"  referrer hosts: " + ", ".join(f"{hh}={c}" for hh, c in d['referrer_hosts']))
    if rows:
        cw = csv.writer(open(os.path.join(hostdir, 'aliases.csv'), 'w', newline=''))
        cw.writerow(['alias', 'target', 'created', 'lifetime_hits', 'hits_24h', 'hits_7d', 'hits_30d',
                     'best_point_label', 'best_point_hits', 'referrer_hosts'])
        for d in rows:
            cw.writerow([d['alias'], d['target'], d['created'], d['lifetime_hits'], d['hits_24h'],
                         d['hits_7d'], d['hits_30d'], d['best_point_label'], d['best_point_hits'],
                         "; ".join(f"{hh}:{c}" for hh, c in d['referrer_hosts'])])
        print(f"\n  -> wrote {os.path.join(hostdir,'aliases.csv')} ({len(rows)} rows)")
