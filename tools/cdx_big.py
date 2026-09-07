#!/usr/bin/env python3
import os,time,urllib.parse,urllib.request,sys
UA='CollusionWikiResearch/1.0 (URL-shortener abuse research)'
OUT='./raw_artifacts/sweep2/wayback/cdx'
jobs=[("prowiki.org","domain","2025b","202505","202509"),
      ("wikiservice.at","domain","2025b","202505","202509"),
      ("pmwiki.org","domain","2025b","202505","202509"),
      ("cde.ucr.cjis.gov","domain","2025b","202505","202509"),
      ("cde.ucr.cjis.gov","domain","2026b","202605","202609")]
for host,mt,tag,fr,to in jobs:
    fn=os.path.join(OUT,f"{host}_{tag}.json")
    if os.path.exists(fn) and os.path.getsize(fn)>0: print("skip",fn); continue
    q={'url':host,'matchType':mt,'from':fr,'to':to,'output':'json','fl':'timestamp,original,statuscode','limit':'200000'}
    u='http://web.archive.org/cdx/search/cdx?'+urllib.parse.urlencode(q)
    print("GET",host,tag,flush=True)
    try:
        req=urllib.request.Request(u,headers={'User-Agent':UA})
        with urllib.request.urlopen(req,timeout=300) as r: b=r.read().decode('utf-8','replace')
        open(fn,'w').write(b); print("  bytes",len(b),flush=True)
    except Exception as e: print("  ERR",e,flush=True)
    time.sleep(2)
print("DONE")
