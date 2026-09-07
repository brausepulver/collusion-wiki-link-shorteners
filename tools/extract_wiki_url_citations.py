#!/usr/bin/env python3
"""Potential wiki mentions: revisions of the collusion-wiki DB that cite a short link's *target* URL directly
(without going through the short link). Reads the link list from dashboard/data.json (so run it after a first
build, like tools/lookup_ip_origin.py), scans every revision body + change summary (raw and percent-decoded),
and writes db_extracts/wiki_url_citations.json:
  exact    {target URL: {n, rows}}        revisions citing the target URL verbatim
  endpoint {host+path: {n, rows}}         revisions citing the same URL ignoring scheme, www., query, fragment, trailing /
  hosts    {host: n}                      revisions citing any URL on that host
n = distinct revisions; rows = up to MAX_ROWS of them (earliest first): [time, label, ip16, wiki, page, found_in, url_as_cited, revision_seq]
(revision_seq is the number after '@' in revision_id, i.e. the #rev-N anchor on collusion.wiki/explorer/page/<wiki>~<page>.html).
Pipeline: build -> this -> build."""
import sqlite3, re, json, html, urllib.parse, collections, os
from urllib.parse import urlsplit
DB = './collusion-wiki.db'; OUT = 'db_extracts/wiki_url_citations.json'; MAX_ROWS = 40
def endpoint(u):
    try: s = urlsplit(u)
    except Exception: return ''
    h = s.netloc.lower()
    if h.startswith('www.'): h = h[4:]
    return h + s.path.rstrip('/')
links = json.load(open('dashboard/data.json'))['links']
T_EXACT = {l['u'] for l in links}; T_EP = {endpoint(l['u']) for l in links} - {''}
urlre = re.compile(r'https?://[^\s"\'<>\]\)|\\}]+')
con = sqlite3.connect(DB)
exact = collections.defaultdict(lambda: {'ids': set(), 'rows': []}); ep = collections.defaultdict(lambda: {'ids': set(), 'rows': []})
hosts = collections.defaultdict(set); nrev = 0
for rid, t, label, ip16, wiki, name, body, summ in con.execute("""SELECT r.revision_id, r.time, r.label, r.ip16, p.wiki, p.name, r.body, r.change_summary
  FROM revisions r JOIN pages p ON p.page_key=r.page_key"""):
    text = html.unescape(body or '') + ' ' + (summ or ''); nrev += 1
    seen = set()
    for src, txt in (('raw', text), ('decoded', urllib.parse.unquote(text))):
        for m in urlre.finditer(txt):
            u = m.group(0).rstrip('.,;:')
            if u in seen: continue
            seen.add(u)
            try: h = (urlsplit(u).hostname or '').lower()
            except Exception: h = ''
            if h: hosts[h].add(rid)
            row = [t, label, ip16, wiki, name, src, u[:300], str(rid).rsplit('@', 1)[-1]]
            if u in T_EXACT and rid not in exact[u]['ids']:
                exact[u]['ids'].add(rid); exact[u]['rows'].append(row)
            e = endpoint(u)
            if e in T_EP and rid not in ep[e]['ids']:
                ep[e]['ids'].add(rid); ep[e]['rows'].append(row)
def pack(d): return {k: {'n': len(v['ids']), 'rows': sorted(v['rows'])[:MAX_ROWS]} for k, v in d.items()}
out = {'n_revisions': nrev, 'max_rows': MAX_ROWS, 'exact': pack(exact), 'endpoint': pack(ep), 'hosts': {h: len(s) for h, s in hosts.items()}}
json.dump(out, open(OUT, 'w'), separators=(',', ':'), sort_keys=True)
print(nrev, 'revisions;', len(links), 'links;', len(out['exact']), 'target URLs cited verbatim;', len(out['endpoint']), 'endpoints;', len(out['hosts']), 'hosts;', os.path.getsize(OUT), 'bytes')
