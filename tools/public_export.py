#!/usr/bin/env python3
"""Build the PUBLIC copy of this repository: the working tree minus the data we hold back.

    python3 tools/public_export.py OUTDIR [--cutoff 2026-08-31] [--window 2026-05-12 2026-07-11]

What is held back (kept locally, never pushed):
  1. Anything dated after --cutoff: link rows, per-day click/access series, Wayback captures, the
     hourly "last 24 h" click samples, the 30-day hit counters read at harvest time.
  2. Everything created from residential / unclassified IPs that are not agent-related. An IP is
     agent-related when it created at least one task/probe/infra link inside the agent window
     (--window). Rows from other such IPs are dropped and the IP never appears in the export.
     Cloud / hosting IPs (Azure, AWS, GCP, Cloudflare, DigitalOcean, Hetzner, TIMEWEB, ...) are kept.
  3. Links obviously not made by the agents: the site owner's own automation and the university
     network (topic kind 'baseline'), the yourls.space operator's post-incident SEO spam, the
     pre-incident history before the dashboard window, and the explicit DROP_IPS below. When in
     doubt a row is kept. For t.mdcdev.me / rmn.re, whose links.csv is the curated agent subset,
     the page dumps and click series follow links.csv. Only aggregate per-day counts of held-back
     rows survive, in <service>/daily_counts.json, so the "full history" timeline still works.
  4. Root-level *.md working notes, full dumps (links_full.csv, vanderbi.lt_tail/), raw stats pages
     and raw referrer pages that embed post-cutoff series.
  5. One third-party leak found in the popcat corpus (a chat.openai.com conversation id).
  6. Everything the dashboard neither reads nor links to (the sweep-2 web/Wayback captures, the
     polling/airtable research captures, paste-site dumps, the extra db_extracts): after the build,
     only the build inputs, the files listed in the dashboard's Raw-data tab and the shortener
     ledgers themselves are kept; the tree is then rebuilt once more to prove it is self-contained.

After filtering, every text file is scanned once more and any held-back IP that still appears
(lookup tables, Wayback captures, prose) is replaced by '[ip withheld]' (or the whole line dropped
in lookup tables). The dashboard is then rebuilt inside OUTDIR from the filtered inputs, and the
result is verified: no held-back IP anywhere, no post-cutoff dates in the data files.
"""
import argparse, collections, csv, glob, json, os, re, shutil, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from topics import classify

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--cutoff', default='2026-08-31', help='last day kept (inclusive, by the timestamp as the dashboard shows it)')
ap.add_argument('--window', nargs=2, default=['2026-05-12', '2026-07-11'], metavar=('FROM', 'TO'), help='agent window used for the agent-related-IP test')
ap.add_argument('--no-build', action='store_true')
args = ap.parse_args()
OUT = os.path.abspath(args.out); CUTOFF = args.cutoff; WIN = tuple(args.window)
WINDOW_START = '2026-05-01'   # same as tools/build_dashboard.py

DROP_IPS = {  # creator IPs whose rows are dropped outright (obviously not the swarm); reason is printed
    '[ip withheld]': 'WorldLink (NP) residential; "view private instagram" SEO spam minted on t.mdcdev.me 2026-06-21',
}
DROP_FILES = [  # glob patterns relative to ROOT, never exported
    '*.md',                                                # root working notes (README included, per instruction)
    'raw_artifacts/shorteners/*/links_full.csv',           # full spam dumps; links.csv already holds the agent rows
    'raw_artifacts/shorteners/vanderbi.lt_tail/**',        # pre-incident tail of the vanderbi.lt dump (counts folded into daily_counts.json)
    'raw_artifacts/shorteners/da.gd/stats/*.html',         # raw stats pages: trailing-60-day series past the cutoff
    'raw_artifacts/shorteners/t.mdcdev.me/stats/*.html',   # raw YOURLS stats pages fetched in September (24 h / 30 d charts)
    'raw_artifacts/shorteners/*/referrers/raw/**',         # raw `+` stats pages of the referrer harvests (same charts; vanderbi.lt's are gitignored anyway)
    'dashboard/alt_services_*', 'dashboard/build_data.py',  # the alt-services ledger page is not linked from the dashboard
]
LINE_DROP_FILES = [  # per-line lookup tables: drop the whole line when it names a held-back IP
    'raw_artifacts/ip_origin/cymru_bulk.txt', 'raw_artifacts/sweep2/asn/*', 'raw_artifacts/shorteners/*/creator_ip_asn.txt',
    'db_extracts/vanderbilt_creator_ips.txt',
]
SERVER_TZ = {'vanderbi.lt': 'America/Chicago'}
def to_utc(ts, tz):
    try: return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%d %H:%M:%S')
    except Exception: return ts

# ---------------- creator-IP origin (same grouping as the dashboard build) ----------------
ORIGIN = json.load(open('raw_artifacts/ip_origin/ip_origin.json')) if os.path.exists('raw_artifacts/ip_origin/ip_origin.json') else {'meta': {}, 'ips': {}}
GROUP_BY_ASN = {8075: 'azure', 16509: 'aws', 14618: 'aws', 396982: 'gcp', 15169: 'gcp', 13335: 'cloudflare', 132892: 'cloudflare',
                14061: 'hosting', 212317: 'hosting', 24940: 'hosting', 400940: 'hosting', 9123: 'hosting'}
def group(ip):
    if ip.startswith(('129.59.', '10.55.')): return 'vanderbilt'
    r = ORIGIN['ips'].get(ip)
    if not r or 'asn' not in r: return 'other'
    g = GROUP_BY_ASN.get(r['asn'])
    if not g: g = 'isp' if not re.search(r'cloud|hosting|server|datacenter|vps', r['org'], re.I) else 'hosting'
    return g
IPV4 = re.compile(r'(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d./])')   # a trailing '/' = already a /16 network
def is_ip4(s): return bool(re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', s or ''))
def is_ip6(s): return bool(s) and ':' in s and bool(re.fullmatch(r'[0-9a-fA-F:.]+', s))
WITHHELD = '[ip withheld]'

# ---------------- files to export ----------------
files = [f for f in subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], capture_output=True, text=True).stdout.split('\n') if f and os.path.isfile(f)]
def dropped_file(f):
    for pat in DROP_FILES:
        if pat.endswith('/**'):
            if glob.fnmatch.fnmatch(f, pat[:-3] + '/*') or f.startswith(pat[:-3] + '/'): return pat
        elif glob.fnmatch.fnmatch(f, pat) and (('/' in pat) == ('/' in f) or '/' in pat): return pat
    return None
def matches_any(f, pats): return any(glob.fnmatch.fnmatch(f, p) for p in pats)
export = [f for f in files if not dropped_file(f)]
dropped_files = [f for f in files if dropped_file(f)]

# ---------------- pass 1: row decisions over every ledger ----------------
def sid_of(f):
    p = f.split('/')
    if p[0] == 'raw_artifacts' and len(p) > 2 and p[1] == 'shorteners': return p[2].replace('vanderbi.lt_tail', 'vanderbi.lt')
    if f.startswith('raw_artifacts/vanderbilt_links_') or f in ('raw_artifacts/y_last.json', 'raw_artifacts/y_bottom.json'): return 'vanderbi.lt'
    return None
def norm_ts(sid, ts):
    ts = (ts or '').strip()
    return to_utc(ts, SERVER_TZ[sid]) if sid in SERVER_TZ and re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', ts) else ts
STATS = collections.defaultdict(collections.Counter)   # file -> reason -> n
KEPT = collections.defaultdict(set)                    # sid -> aliases kept (from the primary ledgers)
ALL_IPS = set(); KEPT_ROWS = []                        # (sid, ts, ip, tk)
def keep_alias(sid, a): return a in KEPT[sid] or (a or '').lower() in KEPT[sid]
DAILY_ADD = collections.defaultdict(collections.Counter)  # sid -> day -> held-back rows (pre-window + baseline, <= cutoff)
UNREL = set()   # residential/unclassified creator IPs with no agent-related link (filled after the first scan)
def decide(sid, ts, ip, url, alias, title):
    """-> 'keep' or the reason for holding the row back"""
    if ts and re.match(r'\d{4}-\d\d-\d\d', ts):
        if ts < WINDOW_START: return 'pre-window'
        if ts[:10] > CUTOFF: return 'post-cutoff'
    if ip in DROP_IPS: return 'drop-ip'
    if ip in UNREL: return 'unrelated-ip'
    tp, tk = classify(url or '', alias or '', title or '', ip or '', None, service=sid or '')
    if tk == 'baseline': return 'baseline'
    return 'keep:' + tk
def row_fields(r):
    alias = r.get('alias') or r.get('keyword') or ''
    su = r.get('shorturl') or r.get('short_url') or ''
    if not alias and su: alias = su.rstrip('/').rsplit('/', 1)[-1]
    return alias, (r.get('timestamp') or r.get('datetime_server_local') or ''), (r.get('ip') or r.get('creator_ip') or ''), (r.get('url') or r.get('long_url_truncated') or ''), (r.get('title') or '')
def ledger_kind(f):
    b = os.path.basename(f)
    if f.endswith('.csv') and (b in ('links.csv', 'agent_links.csv', 'links_raw.csv', 'links_full.csv', 'recent_links.csv') or f.startswith('raw_artifacts/vanderbilt_links_')): return 'csv'
    if '/pages/' in f and f.endswith('.json') or f in ('raw_artifacts/y_last.json', 'raw_artifacts/y_bottom.json') or b == 'pages_p0.json': return 'pages'
    return None
def page_links(f):
    try: d = json.load(open(f))
    except Exception: return None, None
    if isinstance(d, dict) and isinstance(d.get('links'), dict): return d, d['links']
    return None, None
primary = lambda f: os.path.basename(f) == 'links.csv'
CURATED = {sid_of(f) for f in files if os.path.basename(f) == 'links_full.csv'}   # links.csv = curated agent rows; page dumps follow it
def scan():
  STATS.clear(); KEPT.clear(); ALL_IPS.clear(); del KEPT_ROWS[:]; DAILY_ADD.clear()
  for f in sorted(files, key=lambda f: (not primary(f), f)):   # primary ledgers first so KEPT is known when their pages are read
      k = ledger_kind(f); sid = sid_of(f)
      if not k: continue
      rows = []
      if k == 'csv':
          for r in csv.DictReader(open(f, newline='')): rows.append(row_fields(r))
      else:
          d, links = page_links(f)
          if links is None: continue
          for r in links.values(): rows.append(row_fields(r))
      for alias, ts, ip, url, title in rows:
          if ip: ALL_IPS.add(ip)
          dec = decide(sid, norm_ts(sid, ts), ip, url, alias, title)
          if sid in CURATED and os.path.basename(f) not in ('links.csv', 'agent_links.csv') and dec.startswith('keep') and not keep_alias(sid, alias): dec = 'not-in-curated-ledger'
          STATS[f][dec.split(':')[0]] += 1
          if dec.startswith('keep'):
              if f not in dropped_files: KEPT[sid].add(alias); KEPT[sid].add(alias.lower()); KEPT_ROWS.append((sid, norm_ts(sid, ts), ip, dec[5:]))
          elif primary(f) and dec in ('pre-window', 'baseline'): DAILY_ADD[sid][norm_ts(sid, ts)[:10]] += 1
scan()
# agent-related IPs: created a task/probe/infra link inside the agent window; everything else from residential/unclassified IPs goes
agent_ips = {ip for sid, ts, ip, tk in KEPT_ROWS if ip and WIN[0] <= ts[:10] <= WIN[1] and tk in ('task', 'probe', 'infra')}
UNREL.update(ip for _, _, ip, _ in KEPT_ROWS if ip and group(ip) in ('isp', 'other') and ip not in agent_ips and (is_ip4(ip) or is_ip6(ip)))
scan()
kept_ips = {ip for _, _, ip, _ in KEPT_ROWS if ip}
FORBID = {ip for ip in ALL_IPS - kept_ips if group(ip) in ('isp', 'other') and (is_ip4(ip) or is_ip6(ip))} | UNREL
REPL = {ip: WITHHELD for ip in FORBID}
REPL6 = {ip: m for ip, m in REPL.items() if is_ip6(ip)}
def m(ip): return REPL.get(ip, ip)   # only reached for kept rows; their IPs are never in REPL
def scrub_text(s):
    s = IPV4.sub(lambda mm: REPL.get(mm.group(1), mm.group(1)), s)
    for ip, mk in REPL6.items(): s = s.replace(ip, mk)
    s = re.sub(r'chat\.openai\.com/c/[0-9a-f-]{8,}', 'chat.openai.com/c/[redacted]', s)
    s = re.sub(r';? ?contact [\w.+-]+@[\w.-]+\.\w+', '', s)   # research-UA contact clause (personal email) never leaves the machine
    return s

# ---------------- pass 2: write the filtered tree ----------------
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
def outp(f):
    p = os.path.join(OUT, f); os.makedirs(os.path.dirname(p), exist_ok=True); return p
def jdump(obj, p, **kw): json.dump(obj, open(p, 'w'), ensure_ascii=False, **kw)
def filt_days(days):  # [[day, n], ...] or {day: n}
    if isinstance(days, dict): return {d: n for d, n in days.items() if d[:10] <= CUTOFF}
    return [x for x in days if str(x[0])[:10] <= CUTOFF]
def walk_generic(o):
    """alt-services ledger and similar: filter link rows, day series, ip-count lists; mask ips"""
    if isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o):
            if {'alias', 'ip', 't'} <= set(o[0]):
                out = []
                for r in o:
                    dec = decide('vanderbi.lt', r.get('t', ''), r.get('ip', ''), r.get('url', ''), r.get('alias', ''), r.get('title', ''))
                    if dec.startswith('keep'): r = dict(r, ip=m(r['ip'])); out.append(walk_generic(r))
                return out
            if 'k' in o[0] and 'v' in o[0] and any(is_ip4(str(x.get('k'))) for x in o):
                c = collections.Counter()
                for x in o:
                    if str(x['k']) not in REPL: c[str(x['k'])] += x['v']
                return [dict(k=k, v=v) for k, v in c.most_common()]
            if 'd' in o[0] and re.match(r'\d{4}-\d\d-\d\d', str(o[0]['d'])): return [walk_generic(x) for x in o if str(x['d'])[:10] <= CUTOFF]
        return [walk_generic(x) for x in o]
    if isinstance(o, dict): return {k: walk_generic(v) for k, v in o.items()}
    if isinstance(o, str): return scrub_text(o)
    return o
written = {}
for f in export:
    sid = sid_of(f); k = ledger_kind(f); b = os.path.basename(f); p = outp(f)
    if k == 'csv':
        with open(f, newline='') as fh:
            rd = csv.DictReader(fh); rows = list(rd); fields = rd.fieldnames
        keep = []
        for r in rows:
            alias, ts, ip, url, title = row_fields(r)
            if decide(sid, norm_ts(sid, ts), ip, url, alias, title).startswith('keep') and (sid not in CURATED or b in ('links.csv', 'agent_links.csv') or keep_alias(sid, alias)):
                for c in ('ip', 'creator_ip'):
                    if c in r: r[c] = m(r[c])
                keep.append(r)
        with open(p, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(keep)
        written[f] = (len(rows), len(keep))
    elif k == 'pages':
        d, links = page_links(f)
        if links is None: shutil.copy2(f, p); continue
        keep = {}
        for key, r in links.items():
            alias, ts, ip, url, title = row_fields(r)
            if decide(sid, norm_ts(sid, ts), ip, url, alias, title).startswith('keep') and (sid not in CURATED or keep_alias(sid, alias)): keep[key] = dict(r, ip=m(r.get('ip', '')))
        written[f] = (len(links), len(keep))
        if not keep: continue   # nothing left on this page
        d['links'] = keep; jdump(d, p)
    elif b == 'referrers.jsonl':
        n = 0; t = 0
        with open(p, 'w') as w:
            for line in open(f):
                t += 1
                try: rec = json.loads(line)
                except Exception: continue
                if not keep_alias(sid, rec.get('alias', '')): continue
                if rec.get('creator_ip'): rec['creator_ip'] = m(rec['creator_ip'])
                w.write(json.dumps(rec, ensure_ascii=False) + '\n'); n += 1
        written[f] = (t, n)
    elif b == 'referrer_urls.csv':
        with open(f, newline='') as fh:
            rd = csv.DictReader(fh); rows = list(rd); fields = rd.fieldnames
        keep = [dict(r, creator_ip=m(r.get('creator_ip', ''))) for r in rows if keep_alias(sid, r.get('alias', ''))]
        with open(p, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(keep)
        written[f] = (len(rows), len(keep))
    elif b == 'click_series.json':
        cs = json.load(open(f)); out = {}
        for a, r in cs.items():
            if not keep_alias(sid, a): continue
            r = dict(r); r['days'] = filt_days(r.get('days') or []); r.pop('hours', None); out[a] = r
        written[f] = (len(cs), len(out)); jdump(out, p)
    elif f == 'raw_artifacts/shorteners/da.gd/stats.json':
        d = json.load(open(f))
        for a, r in d['aliases'].items():
            if r.get('days'):
                r['days'] = filt_days(r['days']); r['total'] = sum(n for _, n in r['days']); r['span'] = [r['days'][0][0], r['days'][-1][0]] if r['days'] else None
        d['note'] = (d.get('note') or '') + ' [public export: series truncated at %s]' % CUTOFF
        written[f] = (len(d['aliases']), len(d['aliases'])); jdump(d, p)
    elif b == 'per_day_series.json':
        d = json.load(open(f)); out = {}
        for a, r in d.items():
            if not keep_alias(sid, a): continue
            r = dict(r); r['binned_series'] = filt_days(r.get('binned_series') or {}); r.pop('post_disclosure_clicks', None); r['chart_total'] = sum(r['binned_series'].values()); out[a] = r
        written[f] = (len(d), len(out)); jdump(out, p, indent=1)
    elif f == 'raw_artifacts/shorteners/wayback_aliases.json':
        d = json.load(open(f)); cut = CUTOFF.replace('-', '') + '235959'
        for r in d['links'].values():
            caps = [c for c in r.get('captures') or [] if str(c.get('timestamp', ''))[:14] <= cut]
            r['captures'] = caps; r['n'] = len(caps)
            for key in ('first', 'last'):
                if key in r: r[key] = (min if key == 'first' else max)((c['timestamp'] for c in caps), default=None)
        written[f] = (len(d['links']), len(d['links'])); jdump(d, p)
    elif f == 'raw_artifacts/shorteners/vanderbi.lt/reused_links.json':
        d = json.load(open(f))
        for r in d['links']:
            if r.get('creator_ip'): r['creator_ip'] = m(r['creator_ip'])
            for key in ('inwindow_days',):
                if key in r: r[key] = filt_days(r[key])
        written[f] = (len(d['links']), len(d['links'])); jdump(d, p)
    elif f == 'raw_artifacts/shorteners/probe_targets.json':
        d = json.load(open(f))
        for r in d['links']:
            for key in ('days_all', 'days_inwindow'):
                if key in r: r[key] = filt_days(r[key])
            if 'hits_30d_at_harvest' in r: r['hits_30d_at_harvest'] = None   # 30 days before the September harvest: past the cutoff
        written[f] = (len(d['links']), len(d['links'])); jdump(d, p)
    elif f == 'raw_artifacts/ip_origin/ip_origin.json':
        d = json.load(open(f)); ips = {}
        for ip, r in d['ips'].items():
            if ip in kept_ips: ips[ip] = r
        d['ips'] = ips; d['meta'] = dict(d.get('meta', {}), n_ips=len(ips), public_export='held-back creator IPs removed')
        written[f] = (len(json.load(open(f))['ips']), len(ips)); jdump(d, p)
    elif f == 'dashboard/alt_services_data.json':
        d = walk_generic(json.load(open(f))); jdump(d, p, separators=(',', ':')); written[f] = ('json', 'filtered')
    elif f == 'dashboard/alt_services_dashboard.html':
        html = open(f).read(); pre = 'window.__LEDGER__ = '; i = html.find(pre); j = html.find('</script>', i)
        seg = html[i + len(pre):j].strip().rstrip(';')
        d = walk_generic(json.loads(seg))
        html = html[:i + len(pre)] + json.dumps(d, ensure_ascii=False, separators=(',', ':')) + ';\n' + html[j:]
        open(p, 'w').write(scrub_text(html)); written[f] = ('html', 'filtered')
    elif matches_any(f, LINE_DROP_FILES):
        lines = open(f, errors='replace').read().split('\n'); keep = [l for l in lines if not any(ip in REPL for ip in IPV4.findall(l))]
        open(p, 'w').write('\n'.join(keep)); written[f] = (len(lines), len(keep))
    else:
        shutil.copy2(f, p)

# per-service counts of held-back rows (aggregate only) so the build's "full history" timeline is unchanged
for sid, c in DAILY_ADD.items():
    d = os.path.join(OUT, 'raw_artifacts/shorteners', sid)
    if KEPT[sid] and os.path.exists(os.path.join(d, 'links.csv')): jdump(dict(sorted(c.items())), os.path.join(d, 'daily_counts.json'), indent=0)

# ---------------- pass 3: scrub every text file ----------------
BIN = ('.gz', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.db', '.pyc', '.zip', '.woff', '.woff2', '.ico')
scrubbed = []
for dp, dn, fn in os.walk(OUT):
    for name in fn:
        p = os.path.join(dp, name)
        if name.lower().endswith(BIN): continue
        b = open(p, 'rb').read()
        if b'\0' in b[:8192]: continue
        s = b.decode('utf-8', errors='surrogateescape'); s2 = scrub_text(s)
        if s2 != s: open(p, 'wb').write(s2.encode('utf-8', errors='surrogateescape')); scrubbed.append(os.path.relpath(p, OUT))

# ---------------- pass 4: rebuild the dashboard from the filtered inputs ----------------
if not args.no_build:
    r = subprocess.run([sys.executable, 'tools/build_dashboard.py'], cwd=OUT, capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    if r.returncode: sys.exit('build failed in the export')

# ---------------- pass 5: keep only what the dashboard reads or links to ----------------
BUILD_INPUTS = {'raw_artifacts/ip_origin/ip_origin.json', 'raw_artifacts/sweep2/asn/ip16_asn.tsv', 'db_extracts/shortlink_mentions.json',
                'db_extracts/jd_shortlink_mentions.json', 'db_extracts/wiki_url_citations.json', 'db_extracts/wiki_daily.json'}
pruned = []
if not args.no_build:
    dj = json.load(open(os.path.join(OUT, 'dashboard/data.json')))
    refs = set(dj['raw']['files']) | BUILD_INPUTS | {rf for sv in dj['services'] for rf in (sv.get('raw_files') or []) if isinstance(rf, str)}
    for tp in ('dashboard/template.html', 'dashboard/index.html'):
        refs |= set(re.findall(r'(?:raw_artifacts|db_extracts|subagent_reports)/[A-Za-z0-9_./+-]+', open(os.path.join(OUT, tp)).read()))
    for dp, dn, fn in os.walk(OUT):
        for name in fn:
            rel = os.path.relpath(os.path.join(dp, name), OUT)
            if not rel.startswith(('raw_artifacts/', 'db_extracts/', 'subagent_reports/')): continue
            if rel in refs or rel.startswith('raw_artifacts/shorteners/'): continue   # ledgers (already row-filtered) stay whole
            os.remove(os.path.join(dp, name)); pruned.append(rel)
    for dp, dn, fn in os.walk(OUT, topdown=False):
        if not os.listdir(dp) and dp != OUT: os.rmdir(dp)
    before = dict(dj, generated_at=None)
    r = subprocess.run([sys.executable, 'tools/build_dashboard.py'], cwd=OUT, capture_output=True, text=True)
    if r.returncode: print(r.stderr[-1500:]); sys.exit('rebuild after pruning failed: the export is not self-contained')
    after = dict(json.load(open(os.path.join(OUT, 'dashboard/data.json'))), generated_at=None)
    if json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True): sys.exit('rebuild after pruning changed the dashboard data: a build input was pruned')

# ---------------- report + verification ----------------
print('== export:', OUT)
print('files: %d exported, %d dropped' % (len(export), len(dropped_files)))
print('pruned as not used by the dashboard: %d files' % len(pruned), collections.Counter('/'.join(f.split('/')[:2]) for f in pruned).most_common(12))
for f in dropped_files[:12]: print('   dropped', f)
if len(dropped_files) > 12: print('   ... %d more (see DROP_FILES)' % (len(dropped_files) - 12))
print('== row decisions (rows held back by reason):')
for f in sorted(STATS):
    c = STATS[f]; held = {k: v for k, v in c.items() if k != 'keep'}
    if held: print('   %-70s kept %6d  held %s' % (f, c['keep'], dict(held)))
print('== IPs: %d kept; %d held back (residential/unclassified, not agent-related, or only in dropped rows) and withheld wherever they still appear' % (len(kept_ips), len(FORBID)))
for ip in sorted(UNREL):
    r = ORIGIN['ips'].get(ip, {})
    print('   unrelated %-22s %-8s %-45s' % (ip, group(ip), (r.get('org') or '')[:45]))
print('== held-back day counts written:', {s: sum(c.values()) for s, c in DAILY_ADD.items()})
print('== files touched by the final text scrub: %d' % len(scrubbed))
for f in scrubbed[:25]: print('   ', f)
# verify: no held-back IP anywhere, and no post-cutoff dates in the structured data files
bad = collections.Counter(); sep = collections.Counter()
nxt = re.compile(r'2026-(?:09|1[0-2])-\d\d|2026(?:09|1[0-2])\d{2}')
STRUCT = ('.csv', '.jsonl')
for dp, dn, fn in os.walk(OUT):
    for name in fn:
        p = os.path.join(dp, name); rel = os.path.relpath(p, OUT)
        if name.lower().endswith(BIN): continue
        b = open(p, 'rb').read()
        if b'\0' in b[:8192]: continue
        s = b.decode('utf-8', errors='replace')
        for ip in IPV4.findall(s):
            if ip in REPL: bad[rel] += 1
        for ip in REPL6:
            if ip in s: bad[rel] += 1
        if rel.startswith(('raw_artifacts/shorteners/', 'raw_artifacts/y_', 'raw_artifacts/vanderbilt_', 'dashboard/data.json', 'dashboard/alt_services_data.json')) and (rel.endswith(STRUCT) or rel.endswith('.json')):
            n = len(nxt.findall(s))
            if n: sep[rel] += n
print('== VERIFY held-back IPs still present:', dict(bad) if bad else 'none')
print('== VERIFY post-cutoff dates in structured data files:', dict(sep) if sep else 'none')
if bad: sys.exit(2)
