#!/usr/bin/env python3
"""Classify harvested referrer URLs as agent-signature vs post-disclosure contamination.

Referrers on a YOURLS `+` page carry only a count, no timestamp, so they cannot be
dated directly. Instead we separate by CONTENT signature:
  agent  = method-authored strings a researcher's browser would never emit as a Referer
           (reader-proxy chains, data-source API calls, cross-instance yourls mints,
            fabricated marker/inject/ssrf hosts, the instance's own + pages).
  contam = post-disclosure indicators (collusion.wiki, the investigation repos,
           web.archive.org replay, disclosure-era 'for-agents' bait).
  ambig  = spoofed real hosts (google/bing/social) and bare unknowns.

Usage: classify_referrers.py <referrer_urls.csv> [label]
"""
import csv, sys, re, collections

AGENT_HOST = re.compile(r'''(?:^|\.)(
  jqp\.vercel\.app|da\.gd|is\.gd|v\.gd|allorigins\.(?:hexlet\.app|win)|md\.succ\.ai|
  markdown\.new|r\.jina\.ai|pure\.md|corsmirror\.com|corsfix\.com|proxymule\.com|
  cors\.lol|cors\.io|cors\.bwa\.workers\.dev|lemino\.ai|httpbin\.org|httpbingo\.org|
  sec\.gov|dataafrica\.io|worldpoverty\.io|datausa\.io|aihw\.gov\.au|ons\.gov\.uk|
  nationsreportcard\.gov|investor\.gov|usa\.gov|census\.gov|max\.gov|nysed\.gov|
  cbs\.nl|tuik\.gov\.tr|usaspending\.gov|highcharts\.com|
  vanderbi\.lt|uoft\.me|goto\.unm\.edu|u\.ethz\.ch|yourls\.pro|yourls\.website|
  yourls\.space|yourls\.shop|2dd\.pl|bitily\.in|url\.popcat\.xyz|
  urlquery\.net|urlscan\.io|quickchart\.io|raw\.githubusercontent\.com
)(?:[:/]|$)''', re.I | re.X)

# method markers anywhere in the URL (path or query) -> agent
AGENT_MARK = re.compile(r'yourls-(?:api|infos)\.php|action=shorturl|inject|ssrf|'
                        r'county\.json|regcf|__proxy__|\?url=|&url=|marker|canary|'
                        r'fresh[a-z0-9]*=|uniqinject|testuniq|\.local/|\.test/|\.foo/', re.I)
AGENT_EXAMPLE = re.compile(r'//(?:www\.)?example\.(?:com|org|net)(?:[:/]|$)', re.I)

CONTAM = re.compile(r'(?:^|\.)(collusion\.wiki|web\.archive\.org|archive\.org|'
                    r'projectarclight\.org|thecolony\.ai|public-board\.com)(?:[:/]|$)|'
                    r'github\.com/(?:JoshuaDavid|kmad|swarm-ai-research)|'
                    r'WikiAgentSwarm|agent-swarm-forensics', re.I)

AMBIG_HOST = re.compile(r'(?:^|\.)(google\.|bing\.|duckduckgo\.|facebook\.|'
                        r'l\.facebook\.com|lnkd\.in|linkedin\.|t\.co|reddit\.|'
                        r'news\.ycombinator)', re.I)

def classify(url, host):
    if CONTAM.search(url): return 'contam'
    if AGENT_HOST.search(host) or AGENT_HOST.search(url) or AGENT_MARK.search(url) \
       or AGENT_EXAMPLE.search(url): return 'agent'
    if AMBIG_HOST.search(host): return 'ambig-spoof'
    return 'unknown'

def main():
    path = sys.argv[1]; label = sys.argv[2] if len(sys.argv) > 2 else path
    cls_clicks = collections.Counter(); cls_urls = collections.Counter()
    host_clicks = collections.Counter(); contam_rows = []; unknown_hosts = collections.Counter()
    agent_host_clicks = collections.Counter()
    for r in csv.DictReader(open(path)):
        host = r['referrer_host']; url = r['referrer_url']; n = int(r['count'])
        c = classify(url, host)
        cls_clicks[c] += n; cls_urls[c] += 1; host_clicks[host] += n
        if c == 'agent': agent_host_clicks[host] += n
        if c == 'contam': contam_rows.append((n, host, url, r['alias']))
        if c == 'unknown': unknown_hosts[host] += n
    tot = sum(cls_clicks.values())
    print(f'\n===== {label} =====')
    print(f'referred clicks (lifetime): {tot}   distinct referrer URLs: {sum(cls_urls.values())}')
    for c in ('agent', 'contam', 'ambig-spoof', 'unknown'):
        pc = 100*cls_clicks[c]/tot if tot else 0
        print(f'  {c:12} clicks={cls_clicks[c]:7}  ({pc:4.1f}%)  urls={cls_urls[c]}')
    print(' top AGENT referrer hosts:')
    for h, n in agent_host_clicks.most_common(12): print(f'    {n:6}  {h}')
    if contam_rows:
        print(' CONTAMINATION referrers (post-disclosure):')
        for n, h, u, al in sorted(contam_rows, reverse=True)[:20]:
            print(f'    {n:4}  on {al:22} {u[:90]}')
    else:
        print(' CONTAMINATION referrers: none matched')
    print(' top UNKNOWN hosts (review):')
    for h, n in unknown_hosts.most_common(12): print(f'    {n:6}  {h}')

if __name__ == '__main__':
    main()
