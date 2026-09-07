#!/usr/bin/env python3
import os,sys,time,urllib.request,hashlib,json
UA='CollusionWikiResearch/1.0 (URL-shortener abuse research)'
OUT='./raw_artifacts/sweep2/wayback/captures'
os.makedirs(OUT,exist_ok=True)
TARGETS=[
 ("bitily_admin_index","20260601143205","https://bitily.in/MYLABI/admin/"),
 ("bitily_adminajax","20260601143210","https://bitily.in/MYLABI/admin/admin-ajax.php"),
 ("bitily_delete_clarkmementohub56","20260830193242","https://bitily.in/MYLABI/admin/admin-ajax.php?action=delete&keyword=clarkmementohub56&nonce=b2d2743ae3&id=yid1"),
 ("bitily_56cleananchor_stats","20260601142913","https://bitily.in/MYLABI/56cleananchor+"),
 ("bitily_ag1googpuredot8_stats","20260601143151","https://bitily.in/MYLABI/ag1googpuredot8+"),
 ("bitily_readme","20260601143205","https://bitily.in/MYLABI/readme.html"),
 ("yourlspro_create_mineAGPOST2819356","20260527021823","https://yourls.pro/admin/index.php?u=https%3A%2F%2Fexample.org%2FmineAGPOST2819356&k=mineAGPOST2819356"),
 ("yourlswebsite_admin_p1_0521","20260521083316","https://yourls.website/admin/index.php?search_in=all&sort_by=timestamp&sort_order=desc&page=1&perpage=15&total_pages=22&search"),
 ("yourlswebsite_admin_p14_0520","20260520040749","http://yourls.website/admin/index.php?search_in=all&sort_by=timestamp&sort_order=desc&page=14&perpage=15&total_pages=14&search"),
 ("yourlswebsite_admin_p20_0521","20260521065941","https://yourls.website/admin/index.php?search_in=all&sort_by=timestamp&sort_order=desc&page=20&perpage=15&total_pages=20&search"),
 ("yourlswebsite_admin_p3_0520","20260520035741","http://yourls.website/admin/index.php?search_in=all&sort_by=timestamp&sort_order=desc&page=3&perpage=15&total_pages=15&search"),
 ("yourlswebsite_tools","20260520040135","https://yourls.website/admin/tools.php"),
 ("yourlswebsite_kw_1h","20260520043825","http://yourls.website/1h+"),
 ("yourlswebsite_kw_8k","20260520033612","https://yourls.website/8k+"),
 ("wiki_dse_RecentChanges_0622","20260622204148","https://wikiservice.at/dse/wiki.cgi?action=browse&id=RecentChanges&lang=1"),
 ("wiki_dse_RecentChanges_0807","20260807180501","https://wikiservice.at/dse/wiki.cgi?action=browse&id=RecentChanges&lang=1"),
 ("wiki_OECDRegionalRecoveryCO2R6Relay","20260622204148","https://wikiservice.at/dse/wiki.cgi?OECDRegionalRecoveryCO2R6Relay="),
 ("wiki_OECD_backlink_search","20260622204148","https://wikiservice.at/dse/wiki.cgi?bl=on&search=OECDRegionalRecoveryCO2Sequence&title=off&word=on&case=on"),
 ("wiki_diff_OpenAIPovertyOct25Cohort","20260807180513","https://wikiservice.at/dse/wiki.cgi?diff=4&id=OpenAIPovertyOct25Cohort&action=browse"),
 ("wiki_diff_OAIEquityDec30R3","20260807180513","https://wikiservice.at/dse/wiki.cgi?id=OAIEquityDec30R3&action=browse&diff=4"),
 ("wiki_diff_OAIResearchApr14Police2028","20260807180513","https://wikiservice.at/dse/wiki.cgi?action=browse&diff=4&id=OAIResearchApr14Police2028"),
 ("wiki_AgentChunkMassachusettsJune231","20260807180513","https://wikiservice.at/dse/wiki.cgi?AgentChunkMassachusettsJune231="),
 ("prowiki_AgentClarkEcoResearchABC","20260606230142","https://prowiki.org/dse/wiki.cgi?AgentClarkEcoResearchABC"),
 ("prowiki_Agent0SaveDummy7721","20260606223312","https://prowiki.org/dse/wiki.cgi?Agent0SaveDummy7721"),
 ("prowiki_AgentMemVariantsEcon19282","20260606221903","https://prowiki.org/dse/wiki.cgi?AgentMemVariantsEcon19282"),
 ("allorigins_bbmb_saveunique1111","20260527220802","https://allorigins.hexlet.app/raw?url=http%3A%2F%2Fbbmb.gov.in%2Fpower-reports.htm%3Fsaveunique1111"),
 ("allorigins_bbmb_archtest88941","20260527225757","https://allorigins.hexlet.app/raw?url=http%3A%2F%2Fwww.bbmb.gov.in%2Fpower-reports.htm%3Farchtest%3D88941"),
 ("mdsucc_citybouldering","20260526132448","https://md.succ.ai/web.archive.org/web/20250131160900id_/www.citybouldering.co.uk/pricing"),
 ("mdsucc_howlongtobeat6534","20260517163917","https://md.succ.ai/?url=https:%2F%2Fhowlongtobeat.com%2Fgame%2F6534"),
 ("allorigins_httpbin_hexprobe","20260604153827","https://allorigins.hexlet.app/get?url=https%3A%2F%2Fhttpbin.org%2Fanything%2Fc4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c4d5e6f7c"),
]
meta=[]
for name,ts,url in TARGETS:
    fn=os.path.join(OUT,name+'.html')
    if os.path.exists(fn) and os.path.getsize(fn)>0:
        print("skip",name); continue
    u=f"https://web.archive.org/web/{ts}id_/{url}"
    try:
        req=urllib.request.Request(u,headers={'User-Agent':UA})
        with urllib.request.urlopen(req,timeout=120) as r:
            b=r.read(); st=r.status; final=r.geturl()
        open(fn,'wb').write(b)
        print(f"OK {name} {st} {len(b)}b")
        meta.append({'name':name,'ts':ts,'url':url,'wb':u,'status':st,'bytes':len(b),'file':fn})
    except Exception as e:
        print(f"ERR {name} {type(e).__name__} {str(e)[:100]}")
        meta.append({'name':name,'ts':ts,'url':url,'wb':u,'error':str(e)[:200]})
    time.sleep(8)
json.dump(meta,open(os.path.join(OUT,'_manifest.json'),'w'),indent=1)
print("DONE")
