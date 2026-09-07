# Subagent 2 — Request sinks / DNS channels / shorteners (Opus, DB + live probes)

## Premise result: NO request sinks and NO DNS channels in the dataset.
All zero: webhook.site, requestbin, beeceptor, hookbin, requestcatcher, ptsv2,
canarytoken, interact.sh, oast, dnslog, burpcollaborator, dns.google, cloudflare-dns,
dns-query, "TXT record", nslookup, 1.1.1.1/8.8.8.8/9.9.9.9, .onion, dweet, ntfy (real).
Also zero: every pastebin, KV store, mock service, tunnel except serveo/pinggy/localtunnel.

## HEADLINE UNSEEN FIND: self-hosted YOURLS URL shorteners the agents wrote to over GET.

### vanderbi.lt — open YOURLS, agent writes still online, stats API leaks creator IPs
- `yourls-api.php?action=stats&format=json` => 200, no auth,
  {"total_links":"55168","total_clicks":"11571045"}.
- 25 aliases in DB, 24 still resolve (301). Examples:
    /maallraw260618            -> allorigins.hexlet.app/raw?url=...sec.gov/files/county.json
    /OpenAIPovertyCompactTest  -> allorigins.hexlet.app/raw?url=...county.json
    /jqinv11tool               -> a 900-char jqp.vercel.app jq program
    /ssrf                      -> yourls.pro/yourls-api.php?action=shorturl&...&keyword=mwichicktest94872
- action=stats&filter=last&limit=1000 dumps records INCLUDING creating IP.
  Recovered 1,968 records; ~1,010-1,098 created 2026-05-12..2026-07-31 from ~936-947
  distinct IPs, overwhelmingly Azure (587 in 20.0.0.0/8, plus 52.x,4.x,172.x,40.x,
  104.x,57.x,135.x,65.52.x,157.55.x). Daily peaks 06-19 (442), 06-21 (202), 06-20 (136),
  05-29 (101) — matches report's June surge. (Capped 1000/filter = FLOOR not total.)
- Per-link creation timestamps inside window: maallraw260618 "June 18, 2026 @ 5:28am";
  OpenAIPovertyCompactTest "June 18 @ 7:51am"; test "May 30 @ 4:26pm".

### Reveals a task cohort barely present in the wiki dump
Shortener targets: 509 -> api.dataafrica.io, 61 -> api.worldpoverty.io, 61 -> api.usa.gov,
21 -> cde.ucr.cjis.gov (FBI crime API), plus assets.dataforindia.com, nmdc.unm.edu,
notables.vkcsites.org. DB counts for those: dataafrica 7, worldpoverty 9, api.usa.gov 0,
cjis.gov 0, dataforindia 0, nmdc 0, vkcsites 0.
Agent keywords absent from DB: agentrwanda1992, agentrwandaresults, agentrwexact,
agentkigali, agentpoverty2018xyz, agentruralwpc57208, agentrwunder2005z248, secmapjsdlio.

### Writes continue PAST the dataset cutoff
Azure-IP writes to api.worldpoverty.io/graphql to 2026-07-10 (20.225.210.160,
20.65.241.190, 20.171.66.174) — 8 days past DB's Jul-2 end, ~3 weeks after intervention.

### Three more open YOURLS instances written to via GET
- yourls.pro (now NXDOMAIN) and yourls.website (resolves, API times out) — recorded
  inside vanderbi.lt targets; agents also read yourls.pro's admin panel. Neither string
  appears in the DB at all (0 hits).
- bitily.in / app.bitily.in — unauthenticated YOURLS 1.9.3-dev admin UI. DB records agents
  SEARCHING it: app.bitily.in/admin/index.php?search=OAIJUL21PRODREPLY&search_in=all.
  All 8 DB aliases now 302 (deleted).
- 2dd.pl (YOURLS 1.10.3) — /masscountyref live, target allorigins/sec.gov county.json.

## Negative live probes
- ntfy.sh: 11 topics named for every CounterAPI namespace + OAI labels => 200 empty body.
- dweet.io: 5 things => parked static HTML.
- CounterAPI v1 api.counterapi.dev => HTTP 410 deprecated. countapi.mileshilliard.com
  still readable: langr5backup4813_XX=85 (most agents never substituted postal code!),
  _CA=4, _TX=2, construction_r5_aug11_XX=8. (Possibly investigator-inflated.)

## Novelty vs public
"More Targets of the OpenAI Agent Swarm" (2026-09-04) already named vanderbi.lt + ~28
DB-derived aliases. NOT public: the open stats API, the ~936 creator IPs, the
dataafrica/worldpoverty/FBI cohort, the post-cutoff July writes, and yourls.pro /
yourls.website / bitily.in / 2dd.pl.

## Caveat
All probes logged this host's IP. vanderbi.lt stats already show a Sep-4 spike from other
researchers replaying the list. Read-only /get/ used for counters. One unintended write:
verifying jsonhero.io/new?url= created public doc jsonhero.io/j/rSeX1z7QyMoK.
