# Subagent 4 — Wide off-farm venue sweep (Opus, DB + Exa + Wayback + live curl)

## Result: NO unseen venue found. Every trace resolves to the known farm or the report.

## Structural negative from the DB itself
Across all 14,591 bodies the swarm NEVER names a non-farm write venue:
guestbook 0, pastebin 0, etherpad 0, hackmd 0, tiddly 0, dokuwiki 0, moinmoin 0,
pmwiki 0, oddmuse 0, usemod 0, mediawiki 0, fandom 0, miraheze 0, uncyclopedia 0,
publictestwiki 0, shoutbox 0, "another/other/backup wiki" 0. Only meatball once
(inherited interwiki redirect). All 38,750 wiki.cgi? URLs point at the farm.
All 160 agent-minted shortlinks resolve to data/proxy hosts, no unseen venue.

## Two candidates checked and REJECTED as noise
- cliki.net/Agent0 — pre-existing page about "Agent0 programming language by Yoav Shoham",
  matched by the Agent regex.
- twiki.org edit-link `?t=178...` epochs — TWiki's own auto cache-buster, not agent page
  names (any 2026 epoch begins 178). TWiki Sandbox clean, no May-Jul 2026 agent edits.

## Hosts verified CLEAN by direct curl (RecentChanges/index/history)
toothycat.net, dougrice.co.uk, ccgi.dougrice.plus.com, crystalclearsoftware.com boost_wiki,
farnik.com, editthisnft.com, lua-users.org, nipltd.net, wikiweb.at (dead since 2025),
twiki.org Sandbox. Ruled out by construction: foswiki.org (login required), senseis.xmp.net
(referer captcha), alexschroeder.ch + campaignwiki.org (Oddmuse HTTP 402 botcheck — a
GET-only fetcher cannot pass, so this swarm could never have used them).

## Wayback CDX sweeps (2026-05..07, agent-shaped regex) — 0 real hits
senseis.xmp.net, wiki.tcl-lang.org, cliki.net, moinmo.in, wikiindex.org, esolangs.org,
rosettacode.org, wikiweb.at, foswiki.org, twiki.org, toothycat.net, lua-users.org,
dougrice.co.uk, jspwiki-wiki.apache.org.

## Wikimedia sandbox check — 0 rows
en/test/test2.wikipedia.org, wikidata.org, meta.wikimedia.org Sandbox revisions
2026-05-11..06-23. Deprioritized on principle: MediaWiki/DokuWiki/Etherpad/HackMD never
persist on a GET, so this swarm's write path cannot reach them.

## Methodological note
usemod.org/cgi-bin/wiki.pl?SiteList is the canonical directory of live UseMod-family
wikis; walked all live entries (clean). MeatballWiki SwitchWiki/WikiIndex now a stub whose
outbound hosts are all SEEN, dead, or clean.
