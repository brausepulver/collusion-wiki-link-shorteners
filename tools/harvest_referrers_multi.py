#!/usr/bin/env python3
"""Harvest per-alias referrer data from any YOURLS `+` stats page (read-only).

Generalization of harvest_referrers.py to instances beyond vanderbi.lt.
The `+` info page does NOT redirect, so fetching it adds no click to the short link.

Usage:
  harvest_referrers_multi.py <base_url> <links_csv> <out_dir> [--limit N] [--workers K] [--sleep S]

Reads aliases (col 'alias') from <links_csv>, fetches <base>/<alias>+ for each,
writes under <out_dir>/:
  raw/<alias>.html.gz   archived stats page
  referrers.jsonl       one JSON record per alias (summary + host + url breakdown)
  referrer_urls.csv     alias,timestamp,creator_ip,clicks,referrer_host,referrer_url,count
Resumable: skips aliases already in referrers.jsonl.
"""
import csv, sys, os, re, json, gzip, time, html, threading, argparse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, quote
import urllib.request, urllib.error

UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research' + ('; contact ' + os.environ['CONTACT'] if os.environ.get('CONTACT') else '') + ')'  # CONTACT=<email> adds the contact clause

def parse(txt):
    out = {"direct": None, "referrers_total": None, "hosts": [], "urls": []}
    m = re.search(r'yourls_graphstat_tab_source_direct.*?\}', txt, re.S)
    if m:
        for lbl, n in re.findall(r"\[\s*'([^']*)'\s*,\s*(\d+)\s*\]", m.group(0)):
            if lbl == 'Direct': out["direct"] = int(n)
            elif lbl == 'Referrers': out["referrers_total"] = int(n)
    m = re.search(r'yourls_graphstat_tab_source_ref.*?\}', txt, re.S)
    if m:
        for lbl, n in re.findall(r"\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*(\d+)\s*\]", m.group(0)):
            if lbl not in ('Referrer', 'Hits'):
                out["hosts"].append({"host": html.unescape(lbl), "count": int(n)})
    # detail list items use either single- or double-quoted hrefs across YOURLS versions
    for mm in re.finditer(r'<a\s+href=["\']([^"\']+)["\']\s*>[^<]*</a>\s*:\s*(?:<strong>)?\s*(\d+)', txt):
        url = html.unescape(mm.group(1)); n = int(mm.group(2))
        if url and url.startswith(('http://', 'https://')):
            out["urls"].append({"url": url, "count": n})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base'); ap.add_argument('links_csv'); ap.add_argument('out_dir')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--sleep', type=float, default=0.25)
    a = ap.parse_args()
    base = a.base.rstrip('/') + '/'
    RAW = os.path.join(a.out_dir, 'raw'); os.makedirs(RAW, exist_ok=True)
    JSONL = os.path.join(a.out_dir, 'referrers.jsonl')
    URLCSV = os.path.join(a.out_dir, 'referrer_urls.csv')

    rows = {}
    for r in csv.DictReader(open(a.links_csv)):
        al = (r.get('alias') or '').strip()
        if al and al not in rows: rows[al] = r
    rows = list(rows.values())
    rows.sort(key=lambda r: -int(r.get('clicks') or 0))
    if a.limit: rows = rows[:a.limit]

    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try: done.add(json.loads(line)['alias'])
            except: pass
    rows = [r for r in rows if r['alias'] not in done]
    print(f'{len(rows)} aliases to fetch ({len(done)} already done)', flush=True)

    lock = threading.Lock()
    newcsv = not os.path.exists(URLCSV)
    jf = open(JSONL, 'a'); cf = open(URLCSV, 'a', newline='')
    cw = csv.writer(cf)
    if newcsv:
        cw.writerow(['alias', 'timestamp', 'creator_ip', 'clicks',
                     'referrer_host', 'referrer_url', 'count'])
    cnt = [0]

    def fetch(r):
        alias = r['alias']
        url = base + quote(alias) + '+'
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        txt = None; status = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    txt = resp.read().decode('utf-8', 'replace'); status = resp.status
                break
            except urllib.error.HTTPError as e:
                status = e.code; break
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        rec = {'alias': alias, 'timestamp': r.get('timestamp'),
               'creator_ip': r.get('ip') or r.get('creator_ip'),
               'clicks': int(r.get('clicks') or 0), 'status': status}
        if txt is not None:
            with gzip.open(os.path.join(RAW, alias + '.html.gz'), 'wt', encoding='utf-8') as g:
                g.write(txt)
            p = parse(txt); rec.update(p)
        with lock:
            jf.write(json.dumps(rec) + '\n'); jf.flush()
            for u in rec.get('urls', []):
                cw.writerow([alias, rec['timestamp'], rec['creator_ip'], rec['clicks'],
                             urlparse(u['url']).netloc.lower(), u['url'], u['count']])
            cf.flush()
            cnt[0] += 1
            if cnt[0] % 50 == 0: print(f'  {cnt[0]}/{len(rows)}', flush=True)
        time.sleep(a.sleep)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(fetch, rows))
    print('done', flush=True)

if __name__ == '__main__':
    main()
