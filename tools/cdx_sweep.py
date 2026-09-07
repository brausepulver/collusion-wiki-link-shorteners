#!/usr/bin/env python3
import json,os,sys,time,urllib.parse,urllib.request

UA='CollusionWikiResearch/1.0 (URL-shortener abuse research)'
OUT='./raw_artifacts/sweep2/wayback/cdx'
os.makedirs(OUT,exist_ok=True)

TARGETS=[
 ("prowiki.org","domain"),
 ("wikiservice.at","domain"),
 ("vanderbi.lt","domain"),
 ("yourls.pro","domain"),
 ("yourls.website","domain"),
 ("bitily.in","domain"),
 ("2dd.pl","domain"),
 ("api.dataafrica.io","domain"),
 ("api.worldpoverty.io","domain"),
 ("api.usa.gov/crime","prefix"),
 ("cde.ucr.cjis.gov","domain"),
 ("api.counterapi.dev","domain"),
 ("countapi.mileshilliard.com","domain"),
 ("jsonhero.io/j","prefix"),
 ("jqp.vercel.app","domain"),
 ("md.succ.ai","domain"),
 ("allorigins.hexlet.app","domain"),
 ("publictestwiki.com","domain"),
 ("usemod.org","domain"),
 ("pmwiki.org","domain"),
]
WINDOWS=[("2026","202605","202609"),("2025","202505","202509")]

def fetch(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA})
            with urllib.request.urlopen(req,timeout=120) as r:
                return r.read().decode('utf-8',errors='replace'),r.status
        except Exception as e:
            print("  ERR",type(e).__name__,str(e)[:120],file=sys.stderr)
            time.sleep(5*(i+1))
    return None,None

for host,mt in TARGETS:
    for tag,fr,to in WINDOWS:
        slug=host.replace('/','_')
        fn=os.path.join(OUT,f"{slug}_{tag}.json")
        if os.path.exists(fn) and os.path.getsize(fn)>0:
            print("skip",fn); continue
        q={'url':host,'matchType':mt,'from':fr,'to':to,'output':'json',
           'fl':'timestamp,original,statuscode,mimetype,digest','limit':'10000'}
        u='http://web.archive.org/cdx/search/cdx?'+urllib.parse.urlencode(q)
        print("GET",host,tag,flush=True)
        body,st=fetch(u)
        if body is None:
            open(fn+'.failed','w').write(u); continue
        open(fn,'w').write(body)
        try:
            d=json.loads(body) if body.strip() else []
            n=max(0,len(d)-1)
        except Exception:
            n=-1
        print(f"  {host} {tag}: {n} captures",flush=True)
        time.sleep(1.2)
print("DONE")
