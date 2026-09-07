#!/usr/bin/env python3
"""Harvest per-alias referrer data from vanderbi.lt YOURLS `+` stats pages.
Read-only: the `+` info page does NOT redirect, so it does not add clicks.
Outputs (under raw_artifacts/shorteners/vanderbi.lt/referrers/):
  raw/<alias>.html.gz   archived stats page
  referrers.jsonl       one JSON record per alias (summary + host + url breakdown)
  referrer_urls.csv     alias,timestamp,creator_ip,clicks,referrer_host,referrer_url,count
Resumable: skips aliases already present in referrers.jsonl.
Usage: harvest_referrers.py [LIMIT]            agent-era links first, then most-clicked (from links.csv)
       harvest_referrers.py --aliases FILE    one alias per line (e.g. pre-existing links the agents reused); rows not in
                                              links.csv (pre-2012 keywords such as iyg1y) are looked up via the url-stats API.
CONTACT=<email> appends a contact clause to the UA.
"""
import csv, sys, os, re, json, gzip, time, html, threading
from concurrent.futures import ThreadPoolExecutor
import urllib.request, urllib.error

BASE="https://vanderbi.lt/"
UA="CollusionWikiResearch/1.0 (URL-shortener abuse research"+("; contact "+os.environ["CONTACT"] if os.environ.get("CONTACT") else "")+")"
ROOT="raw_artifacts/shorteners/vanderbi.lt/referrers"
RAW=os.path.join(ROOT,"raw")
JSONL=os.path.join(ROOT,"referrers.jsonl")
URLCSV=os.path.join(ROOT,"referrer_urls.csv")

def clk(r):
    try: return int(r['clicks'])
    except: return 0

def load_aliases():
    seen={}
    for path in ["raw_artifacts/shorteners/vanderbi.lt/links.csv",
                 "raw_artifacts/shorteners/vanderbi.lt_tail/links.csv"]:
        if not os.path.exists(path): continue
        for r in csv.DictReader(open(path)):
            a=r['alias']
            if not a: continue
            if a not in seen or clk(r)>clk(seen[a]): seen[a]=r
    rows=[r for r in seen.values() if clk(r)>=1]
    # agent-era first (>=2026-05-01), then most-clicked
    rows.sort(key=lambda r:(r['timestamp']<'2026-05-01', -clk(r)))
    return rows

def parse(txt):
    out={"direct":None,"referrers_total":None,"hosts":[],"urls":[]}
    # Direct vs Referrers
    m=re.search(r'yourls_graphstat_tab_source_direct.*?\}',txt,re.S)
    if m:
        for lbl,n in re.findall(r"\[\s*'([^']*)'\s*,\s*(\d+)\s*\]",m.group(0)):
            if lbl=='Direct': out["direct"]=int(n)
            elif lbl=='Referrers': out["referrers_total"]=int(n)
    # per-host aggregate (pie): host -> count
    m=re.search(r'yourls_graphstat_tab_source_ref.*?\}',txt,re.S)
    if m:
        for lbl,n in re.findall(r"\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*(\d+)\s*\]",m.group(0)):
            if lbl not in ('Referrer','Hits'):
                out["hosts"].append({"host":html.unescape(lbl),"count":int(n)})
    # detailed per-URL list: <li><a href='URL' >URL</a>: N</li>  and sites_HOST headers
    for mm in re.finditer(r"<a href='([^']*)'[^>]*>[^<]*</a>\s*:\s*(?:<strong>)?(\d+)",txt):
        url=html.unescape(mm.group(1)); n=int(mm.group(2))
        if url: out["urls"].append({"url":url,"count":n})
    return out

lock=threading.Lock()
done=set()
if os.path.exists(JSONL):
    for line in open(JSONL):
        try: done.add(json.loads(line)["alias"])
        except: pass

def fetch(alias):
    url=BASE+urllib.parse.quote(alias)+"+"
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=30) as resp:
                return resp.read().decode("utf-8","replace"),resp.status
        except urllib.error.HTTPError as e:
            return None,e.code
        except Exception:
            time.sleep(1.5*(attempt+1))
    return None,0

import urllib.parse
def work(r):
    a=r['alias']
    if a in done: return "skip"
    txt,status=fetch(a)
    if txt is None:
        with lock:
            open(JSONL,"a").write(json.dumps({"alias":a,"error":status})+"\n")
        return f"err{status}"
    # archive raw
    try:
        with gzip.open(os.path.join(RAW,a.replace('/','_')+".html.gz"),"wt",encoding="utf-8") as f:
            f.write(txt)
    except Exception: pass
    p=parse(txt)
    rec={"alias":a,"timestamp":r['timestamp'],"creator_ip":r['ip'],
         "clicks":clk(r),"target":r['url'],
         "direct":p["direct"],"referrers_total":p["referrers_total"],
         "hosts":p["hosts"],"urls":p["urls"]}
    with lock:
        open(JSONL,"a").write(json.dumps(rec,ensure_ascii=False)+"\n")
        w=csv.writer(open(URLCSV,"a",newline=""))
        for u in p["urls"]:
            host=re.sub(r'^https?://','',u["url"]).split('/')[0]
            w.writerow([a,r['timestamp'],r['ip'],clk(r),host,u["url"],u["count"]])
    return "ok"

def urlstats(alias):
    """url-stats API row for an alias that links.csv lacks (the paginated pull never reached pre-2012 offsets)"""
    url=BASE+"yourls-api.php?action=url-stats&format=json&shorturl="+urllib.parse.quote(alias)
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp: d=json.loads(resp.read().decode("utf-8","replace"))
        l=d.get("link") or {}
        if l.get("url") is None: return None
        return dict(alias=alias,timestamp=l.get("timestamp",""),ip=l.get("ip",""),clicks=l.get("clicks",0),title=l.get("title",""),url=l.get("url",""),shorturl=l.get("shorturl",""))
    except Exception: return None

def main():
    if len(sys.argv)>2 and sys.argv[1]=="--aliases":
        want=[l.strip() for l in open(sys.argv[2]) if l.strip() and not l.startswith('#')]
        byalias={r['alias']:r for r in load_aliases()}
        rows=[]
        for a in want:
            r=byalias.get(a) or urlstats(a)
            if r: rows.append(r)
            else: print("  no such alias:",a,flush=True)
    else:
        rows=load_aliases()
        limit=int(sys.argv[1]) if len(sys.argv)>1 else len(rows)
        rows=rows[:limit]
    if not os.path.exists(URLCSV):
        csv.writer(open(URLCSV,"w",newline="")).writerow(
            ["alias","timestamp","creator_ip","clicks","referrer_host","referrer_url","count"])
    print(f"aliases to process: {len(rows)} (already done: {len(done)})",flush=True)
    n=ok=err=0; t0=time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for res in ex.map(work,rows):
            n+=1
            if res=="ok": ok+=1
            elif res.startswith("err"): err+=1
            if n%200==0:
                dt=time.time()-t0
                print(f"  {n}/{len(rows)}  ok={ok} err={err}  {n/dt:.1f}/s  eta={ (len(rows)-n)/(n/dt)/60:.0f}m",flush=True)
    print(f"DONE n={n} ok={ok} err={err} in {(time.time()-t0)/60:.1f}m",flush=True)

if __name__=="__main__": main()
