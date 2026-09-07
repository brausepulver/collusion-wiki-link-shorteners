#!/usr/bin/env python3
"""Resolve creator IPs (from dashboard/data.json) to origin: ASN/org via Team Cymru bulk whois, Azure region via
Microsoft's public Service Tags file, and membership in published AI-agent egress ranges (OpenAI, Perplexity).
Writes raw_artifacts/ip_origin/{cymru_bulk.txt, ServiceTags_Public_*.json, *.json ranges, ip_origin.json}.
Re-runs are incremental: only IPs missing from cymru_bulk.txt are queried."""
import json, os, socket, subprocess, sys, time, glob, ipaddress, urllib.request, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
UA = 'CollusionWikiResearch/1.0 (URL-shortener abuse research)'
OUT = 'raw_artifacts/ip_origin'; os.makedirs(OUT, exist_ok=True)
RANGES = {'OpenAI ChatGPT-User / Operator': 'https://openai.com/chatgpt-user.json', 'OpenAI GPTBot': 'https://openai.com/gptbot.json',
          'OpenAI OAI-SearchBot': 'https://openai.com/searchbot.json', 'PerplexityBot': 'https://www.perplexity.com/perplexitybot.json',
          'Perplexity-User': 'https://www.perplexity.com/perplexity-user.json'}
def fetch(url, dest):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r: data = r.read()
    open(dest, 'wb').write(data); return data
ips = sorted({l['ip'] for l in json.load(open('dashboard/data.json'))['links']})
# 1. Team Cymru bulk whois (ASN + org)
cym = os.path.join(OUT, 'cymru_bulk.txt'); have = set()
if os.path.exists(cym):
    for line in open(cym):
        f = [x.strip() for x in line.split('|')]
        if len(f) > 6: have.add(f[1])
todo = [ip for ip in ips if ip not in have]
if todo:
    print('cymru lookup for', len(todo), 'ips', file=sys.stderr)
    q = 'begin\nverbose\n' + '\n'.join(todo) + '\nend\n'
    res = subprocess.run(['nc', 'whois.cymru.com', '43'], input=q.encode(), capture_output=True, timeout=300).stdout.decode()
    body = res if not have else '\n'.join(l for l in res.splitlines() if not l.startswith('Bulk mode')) + '\n'
    with open(cym, 'a') as f: f.write(body)
asn = {}
for line in open(cym):
    f = [x.strip() for x in line.split('|')]
    if len(f) > 6 and f[0].isdigit(): asn[f[1]] = dict(asn=int(f[0]), prefix=f[2], cc=f[3], org=f[6])
# 2. Azure service tags (weekly file; try the most recent Mondays)
st_files = sorted(glob.glob(os.path.join(OUT, 'ServiceTags_Public_*.json')))
if not st_files:
    import datetime
    d = datetime.date.today()
    for back in range(0, 21):
        day = d - datetime.timedelta(days=back)
        if day.weekday() != 0: continue
        url = f"https://download.microsoft.com/download/7/1/D/71D86715-5596-4529-9B13-DA13A5DE5B63/ServiceTags_Public_{day:%Y%m%d}.json"
        try: fetch(url, os.path.join(OUT, f'ServiceTags_Public_{day:%Y%m%d}.json')); st_files = [os.path.join(OUT, f'ServiceTags_Public_{day:%Y%m%d}.json')]; break
        except Exception as e: print('no service tags for', day, e, file=sys.stderr)
st = json.load(open(st_files[-1])) if st_files else {'values': []}
by1 = collections.defaultdict(list)
for v in st['values']:
    p = v['properties']
    for pre in p['addressPrefixes']:
        if ':' in pre: continue
        n = ipaddress.ip_network(pre); by1[int(n.network_address) >> 24].append((n, v['name'], p.get('region', ''), p.get('systemService', '')))
# 3. published agent egress ranges
nets = {}; meta_ranges = {}
for name, url in RANGES.items():
    dest = os.path.join(OUT, url.split('//')[1].replace('/', '_'))
    if not os.path.exists(dest):
        try: fetch(url, dest)
        except Exception as e: print('range fetch failed', url, e, file=sys.stderr); continue
    j = json.load(open(dest)); nets[name] = [ipaddress.ip_network(p['ipv4Prefix']) for p in j.get('prefixes', []) if 'ipv4Prefix' in p]
    meta_ranges[name] = dict(url=url, prefixes=len(nets[name]), fetched=time.strftime('%Y-%m-%d', time.gmtime(os.path.getmtime(dest))), hit_ips=0)
# 4. per-IP record
out = {}
for ip in ips:
    rec = dict(asn.get(ip, {})); rec['region'] = ''; rec['tags'] = []; rec['published'] = []
    try: a = ipaddress.ip_address(ip)
    except ValueError: out[ip] = rec; continue
    if a.version == 4:
        m = sorted([e for e in by1[int(a) >> 24] if a in e[0]], key=lambda e: -e[0].prefixlen)
        rec['region'] = next((e[2] for e in m if e[2]), ''); rec['service'] = next((e[3] for e in m if e[3]), ''); rec['tags'] = [e[1] for e in m][:4]
        for name, ns in nets.items():
            if any(a in n for n in ns): rec['published'].append(name); meta_ranges[name]['hit_ips'] += 1
    out[ip] = rec
meta = dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), n_ips=len(ips), asn_source='Team Cymru IP-to-ASN bulk whois (whois.cymru.com)',
            azure_tags=dict(file=os.path.basename(st_files[-1]) if st_files else None, changeNumber=st.get('changeNumber')), published_ranges=meta_ranges)
json.dump(dict(meta=meta, ips=out), open(os.path.join(OUT, 'ip_origin.json'), 'w'), indent=0)
print(json.dumps(meta, indent=1)); print('asn groups', collections.Counter(r.get('org', '?')[:40] for r in out.values()).most_common(20))
