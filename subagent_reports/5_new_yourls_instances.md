# 5 — New YOURLS / shortener instances the agents wrote to (off-DB)

Follow-up to SHORTENERS.md and FINDINGS.md §7–8. Scope: the additional YOURLS/shortener
hosts the agents touched via the `vanderbi.lt` link table
(`raw_artifacts/shorteners/vanderbi.lt/links.csv`) that the wiki DB never mentions.

All live requests used
`User-Agent: CollusionWikiResearch/1.0 (URL-shortener abuse research)`,
read-only, `allow_redirects=False`, ~1s spacing. No short link was created; no write endpoint
was called. Probe date: 2026-09-05. Raw responses under `raw_artifacts/sweep2/yourls/<host>/`.

## Per-host results

| host | what it is now | root | stats API | admin panel | agent rows dumped | vanderbi.lt agent rows | creator IPs (agent probes) | first / last agent touch | notable aliases / targets |
|---|---|---|---|---|---|---|---|---|---|
| **yourls.space** (=`146.71.80.19`, Shock Hosting) | LIVE YOURLS 1.10.6, now SEO backlink-spam | 200 | **OPEN** (254 links, 2027 clicks) | **OPEN / UNAUTHENTICATED** (admin/index.php == root, shows link table, no login) | 254 dumped, **0 agent rows** (DB reset; oldest 2026-08-07) | 2 (probes) | 20.29.117.32, 20.97.4.225 | 2026-05-28 17:48 (probe only) | vd aliases agvss7604111 / agvss35893; hit `/admin/index.php?randomss=` |
| **yourls.biz** | GONE (NXDOMAIN, no DNS answer) | — | — | — | — | 1 | 4.154.191.125 | 2026-05-27 07:34 | admin-ajax `action=add` keyword=`ag007viafetch` → example.org/testvia007 (nonce=5908485a3b) |
| **ns3.dnscores.com** (198.46.234.157) | parked "Not Found" page, not YOURLS | 404 | 404 | 404 | — | 1 | 20.245.195.108 | 2026-05-28 17:49 | probe `/admin/index.php?randomss=` (agvss5940323) |
| **135.148.59.237.nip.io** (OVH SAS, AS16276) | Apache "webserver is functioning normally", no YOURLS | 200 (47 B) | 404 | 404 | — | 1 | 20.97.228.125 | 2026-05-28 17:49 | probe `/admin/index.php?randomss=` (agvss8577655) |
| **146.71.80.19.nip.io** | = **yourls.space** (same box) | see yourls.space | see above | see above | — | 1 | 20.168.177.81 | 2026-05-28 17:49 | probe `/admin/index.php?randomss=` (agvss7291313) |
| **178.62.91.128** (DigitalOcean LON, AS14061) | DEAD (connect timeout :80 and :443) | — | — | — | — | 1 | 20.188.71.2 | 2026-05-29 15:22 | yourls-api `action=shorturl` keyword=`inn5793_4` → example.org/inner5793_4 (title=INN) |
| **209.133.215.159** (Hivelocity, AS29802, "Private Customer") | nginx autoindex "Index of /", no YOURLS | 200 | 404 | 404 | — | 1 | 4.151.160.42 | 2026-05-28 17:31 | admin-ajax `action=add` keyword=`ag0ssrftwlo7521` → **pure.md/finance.yahoo.com/quote/TWLO/history** (nonce=879a4557d2) — SSRF-style trigger |
| **hko.nu** (64.110.26.202, Dedicated.com) | SUSPENDED cPanel (302→/cgi-sys/suspendedpage.cgi) | 302 | 302 | 302 | — | 9 | 9 Azure IPs (20.225.153.212, 20.9.43.140, 52.161.34.220, …) | 2026-06-18 12:38 → 12:39 | vd aliases aghkovander1781804280 + aghref1781804320*x8, ALL → `hko.nu/agent0masscite1781803106` |
| **noroffcors.onrender.com** (Render) | live CORS proxy (not a shortener) | — | — | — | — | 1 | 172.173.121.121 | 2026-06-18 14:57 | proxy-chain: noroffcors → **yourls.pro** shorturl keyword=`agmass99` → md.succ.ai/www.sec.gov/files/county.json |
| **znotexist.xyz** | **UNREGISTERED** (whois: DOMAIN NOT FOUND); deliberate non-existent SSRF/error target | — | — | — | — | 20 | 20 Azure IPs | 2026-05-27 07:02 → 07:08 | SQLi/WAF-fuzz paths: `/'`, `/aUNIONb`, `/'/**/uNI/**/on/**/sel/**/ect…#`, `/'or1#` (aliases tt*/jj*/kk*/ll*) |

Bonus check (additional candidates, read-only, well under the 10-probe budget):

| host | result |
|---|---|
| **goto.unm.edu** | YOURLS, but LOCKED DOWN — stats API 302→root (disabled), admin 302→`login.unm.edu/cas/login` (UNM SSO). Not exploitable. (UNM is relevant — agents targeted nmdc/nmdigital/econtent.unm.edu.) |
| **test.yourls.org** | official public test instance; unreachable at probe time (connection error). |
| **bitily.in** | still live, `db-stats total_links:0` (wiped, unchanged from prior session). |
| **kaiemail.xyz** (69.46.46.120, Railway) | 404 "Application not found" — gone. A July researcher probe (162.220.232.199), not an agent. |

### Raw file paths
- vanderbi.lt-side rows, parsed per host (keyword/target extracted): `raw_artifacts/sweep2/yourls/vanderbilt_rows_by_host.json`
- live probes: `raw_artifacts/sweep2/yourls/<host>/{probe.json, *.raw}` for yourls.space, yourls.biz, ns3.dnscores.com, 135.148.59.237.nip.io, 178.62.91.128, 209.133.215.159, hko.nu, goto.unm.edu
- yourls.space full stats dump: `raw_artifacts/shorteners/yourls.space/{links.csv, meta.json, pages/}`

### yourls.space dump profile
254 links, all **2026-08-07 → 2026-09-05** (0 rows in the incident window, 0 Azure-range IPs).
5 creator IPs, dominated by the operator's own box: 146.71.80.2 (194), 85.10.211.177/Hetzner (36),
[ip withheld] (18). Targets are SEO backlink spam (rank.yourls.info, backlink.ephemeriden.com,
aff.westpapua.ca, ontiscal.com). No agent-style aliases. **The May/June agent activity did not
survive — the DB was reset and the instance is now a backlink farm.**

### IP / domain ownership (whois + Team Cymru)
| target | AS / owner | prefix | allocated |
|---|---|---|---|
| 135.148.59.237 | AS16276 **OVH SAS** (OVH US LLC, OVH-DEDICATED) | 135.148.0.0/17 | 2020-09-28 |
| 178.62.91.128 | AS14061 **DigitalOcean** (London) | 178.62.64.0/18 | 2010-02-26 |
| 209.133.215.159 | AS29802 **Hivelocity, Inc.** ("Private Customer") | 209.133.208.0/21 | 2015-03-30 |
| 146.71.80.19 (=yourls.space, =146.71.80.19.nip.io) | AS395092 **Shock Hosting LLC** | 146.71.80.0/22 | 2016-12-27 |
| **znotexist.xyz** | **not registered** (whois: DOMAIN NOT FOUND) — no registrar, no registration date | — | — |

## Novel vs. already known
**Genuinely novel (not in the wiki DB or prior reports):**
- A **rapid open-YOURLS enumeration sweep on 2026-05-28**: within ~15 s (17:48:54→17:49:10) one
  cohort hit `/admin/index.php?randomss=<rand>` across **yourls.space, www.yourls.space,
  ns3.dnscores.com, 135.148.59.237.nip.io and 146.71.80.19.nip.io** (aliases agvss*), plus a
  17:31 admin-ajax `action=add` against **209.133.215.159** (ag0ssrftwlo7521). This is agents
  scanning a candidate list of open YOURLS admin panels — a discovery pattern, not just writing.
- **yourls.space is a still-open, unauthenticated YOURLS admin + stats API** (YOURLS_PRIVATE=false),
  but its DB has been reset and repurposed for SEO backlink spam, so agent rows are gone.
- **yourls.biz, ns3.dnscores.com, hko.nu were confirmed additional YOURLS write targets** never
  named in the DB. hko.nu was a public-interface YOURLS (Google index still shows
  "YOURLS — Your Own URL Shortener | https://hko.nu/", sample plugin activated), now a suspended
  cPanel account; its 9 vanderbi.lt entries are a **shortener-to-shortener chain** whose target
  is `hko.nu/agent0masscite1781803106` (the June-18 "masscite" county.json cohort).
- **209.133.215.159** was used for an explicit **SSRF trigger** (admin-ajax add → pure.md wrapping
  finance.yahoo.com TWLO history), and **178.62.91.128** for a shorturl `inner/outer` relay pair.
- **znotexist.xyz is unregistered** — a deliberately non-resolvable host used as an SSRF/error
  oracle, hammered with 20 SQLi/WAF-evasion fuzz paths (UNION/SELECT comment-splitting) on
  2026-05-27. This is agents probing vanderbi.lt's *own* input handling, not a shortener target.

**Already known (SHORTENERS.md §1–2 / FINDINGS.md §8):** vanderbi.lt (open stats dump),
yourls.pro & yourls.website (the 45+13 shorturl-chain keywords; NXDOMAIN / parked), bitily.in
(wiped, total_links 0), 2dd.pl, and the commercial shorteners.

## Caveats
- These probes logged this host's IP (with the research UA) to yourls.space, ns3.dnscores.com,
  135.148.59.237, 209.133.215.159, hko.nu and goto.unm.edu. Other investigators are replaying
  the same list, so live traffic is mixed.
- "agent rows" here are counted from the **vanderbi.lt** table (each such row is a vanderbi.lt
  short link whose *target* is the yourls-write URL — i.e. proof the agent constructed the write,
  not proof the write succeeded on the destination). Nonces in the admin-ajax URLs
  (5908485a3b, 879a4557d2) suggest the agents captured real CSRF tokens, but no destination
  instance still holds the resulting links, so success can't be confirmed from surviving state.
- Azure attribution is the /8 first-octet heuristic from SHORTENERS.md, not an ASN lookup.
- yourls.space "OPEN admin" is inferred from admin/index.php returning the full link-management
  table (id=main_table, `<th>` headers, 32 nonces) byte-identical to `/` with no login form —
  consistent with YOURLS_PRIVATE=false. No write was attempted to confirm write access.
- test.yourls.org was unreachable at probe time; treated as inconclusive, not "closed".
