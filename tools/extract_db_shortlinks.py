#!/usr/bin/env python3
"""Extract every shortener URL mentioned in the collusion-wiki DB, with revision context."""
import sqlite3, re, json, html, urllib.parse, sys
DB = './collusion-wiki.db'
HOSTS = ['vanderbi.lt','tinyurl.com','is.gd','v.gd','da.gd','bitily.in','ctxr.me','2dd.pl',
         'yourls.pro','yourls.website','short.kodact.art','bit.ly','t.co','goo.gl','cutt.ly','rb.gy','shorturl.at','tiny.cc','t.ly']
pat = re.compile(r'https?://(?:www\.|app\.)?(' + '|'.join(re.escape(h) for h in HOSTS) + r')(/[^\s"\'<>\]\)|\\]*)?', re.I)
con = sqlite3.connect(DB)
rows = con.execute("""SELECT r.revision_id, r.time, r.label, r.ip16, p.wiki, p.name, r.body, r.change_summary
  FROM revisions r JOIN pages p ON p.page_key=r.page_key""")
out = []
for rid, t, label, ip16, wiki, name, body, summ in rows:
    text = html.unescape(body or '') + ' ' + (summ or '')
    # also percent-decoded pass (links inside proxy wrappers)
    dec = urllib.parse.unquote(text)
    seen = set()
    for src, txt in (('raw', text), ('decoded', dec)):
        for m in pat.finditer(txt):
            u = m.group(0).rstrip('.,;:')
            host = m.group(1).lower()
            path = (m.group(2) or '')
            segs = [x.split('?')[0].split('&')[0].split('#')[0] for x in path.strip('/').split('/')] if path else ['']
            # bitily.in ran under a /MYLABI/ prefix: the keyword is the second path segment
            alias = '/'.join(segs[:2]) if host == 'bitily.in' and segs[0].upper() == 'MYLABI' and len(segs) > 1 and segs[1] else segs[0]
            if host == 'tinyurl.com' and segs[0].lower() in ('preview', 'preview.php'): alias = segs[1] if len(segs) > 1 else ''  # tinyurl.com/preview/ALIAS
            key = (host, alias or path)
            if key in seen: continue
            seen.add(key)
            out.append(dict(revision_id=rid, time=t, label=label, ip16=ip16, wiki=wiki, page=name,
                            host=host, alias=alias, url=u[:400], found_in=src))
out.sort(key=lambda r: r['time'])
json.dump(out, open('db_extracts/shortlink_mentions.json','w'), indent=0)
import collections
print(len(out), 'mentions;', len({(r['host'],r['alias']) for r in out}), 'distinct host+alias')
print(collections.Counter(r['host'] for r in out).most_common())
print('labels:', len({r['label'] for r in out}), 'pages:', len({r['page'] for r in out}))
