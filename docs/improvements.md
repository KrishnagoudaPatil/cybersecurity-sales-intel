# Improvement Backlog

Open work, prioritised by leverage. (Completed work isn't tracked here — see the git history.)

## Entity resolution (highest leverage)
The biggest source of error: mapping scanned hosts to the real company that owns them. The
attribution is a confidence-ranked waterfall (TLS cert → reverse-DNS, with hosting/CDN/telco
orgs distrusted) and a deliberate **precision-over-recall** choice — it attributes a minority
of services to *real* companies rather than inflating recall with hosting artifacts. High
recall is exactly what produces phantom mega-companies (a reverse-DNS-only model attributed
`incapdns.net` = 21,407 hosts); for a sales worklist, a smaller set of real accounts beats a
large one full of hosting noise. The items below lift recall **without** reintroducing phantoms.

1. **Parse the TLS SAN, not just the CN.** Cert coverage is only ~9% on `subject.CN` alone;
   the Subject Alternative Name lists further domains and would raise cert-based recall.
   Skipped so far because Shodan stores SAN as raw ASN.1 bytes in `ssl.cert.extensions[].data`
   — extract the DNS names with a regex. *Effort:* Medium.
2. **Infra detection via ASN, and measure its false positives.** Reverse-DNS is distrusted
   when the host's `org` matches the `infra_org_patterns` seed (hosting/CDN/telco substrings).
   Upgrade to (a) a curated **hosting-ASN list** rather than fuzzy org strings, for higher
   precision; and (b) **measure false positives** — provider orgs can host a provider's own
   corporate servers (real prospects); the cert path should rescue those, but confirm how many
   cert-less hosts on provider orgs get discarded. *Effort:* Medium.
3. **Passive / forward DNS enrichment.** Shodan gives reverse DNS; a passive-DNS source gives
   which domains point *to* an IP. Use it to attribute no-domain, no-cert hosts. *Impact:*
   Medium. *Effort:* Medium/High.
4. **"Unattributed exposures" bucket.** Don't discard services with findings but no company —
   keep them in a separate model for an ops view and later matching. *Impact:* Medium.
   *Effort:* Low.
5. **Full Public Suffix List as a seed.** `registrable_domain` uses a hand-curated
   two-level-suffix set (a PSL stand-in); loading the real PSL removes the bare-eTLD leakers
   (`ne.jp`, `net.id`, …) for good. *Effort:* Low/Medium.
6. **Appliance / default-cert blocklist.** Some hosts present default certs whose subject is a
   vendor/placeholder (`localhost.localdomain`, `Fortinet`, `Acme Co`, `HTTPS Management
   Certificate`); reserved TLDs and placeholders are already filtered, but a small default-cert
   blocklist would catch the rest. *Effort:* Trivial.

## Signal quality
7. **CVE severity (CVSS) weighting.** Today all CVEs count equally; enrich with CVSS so a
   critical RCE outranks a low-severity issue. *Effort:* Medium.
8. **Robust header parsing.** Current missing-header checks use a lowercased key string + LIKE;
   move to structured key iteration for edge cases.
9. **Tiny-footprint accounts score too high.** A 1-host company with a couple of CVEs can reach
   tier A because `risk_score` caps near 100 regardless of footprint size. Consider scaling
   risk by footprint/confidence, or a minimum-evidence floor, so single-host shells don't crowd
   out substantial prospects. *Effort:* Low.

## Scale & operations
10. **Snowpipe + clustering for continuous ingest.** The full 74 GB loads via an S3 external
    stage today; add Snowpipe for continuous/auto ingest and cluster `RAW.SCANS` by scan date.
    *Effort:* Medium.
11. **Incremental models** so re-runs process only new scan dates.

## AI-native & product
12. **Buying-signal (intent) view — the "who to call now" verdict.** The task frames the core
    problem around *buying signals*: which accounts need us *right now*. Add a third detail-view
    action beside Summary and Outreach that returns an intent verdict — `HIGH / MEDIUM / LOW`,
    the 2–3 drivers behind it, and a recommended action (call this week / sequence / nurture).
    Design principle: **compute it as a rule, not an LLM feature** — intent is prospect
    prioritization that must be auditable and runs across the whole book, so it belongs in SQL,
    not a per-account paid call. Proposed deterministic intent score (a new `intent_score` /
    `intent_tier` column on `FCT_ACCOUNT_SCORE`), weighting concrete/urgent exposure over
    hygiene and scaling by ICP fit:
    `intent_raw = 3·exposed_db + 3·min(cve_count, cap) + 2·exposed_remote + 1·eol
    + 0.5·weak_tls + 0.25·missing_header_ratio`, then `intent = normalize(intent_raw) ·
    fit_multiplier(0.7–1.0)`, bucketed into tiers. An exposed database or active CVEs is a
    "call today" driver; missing headers is "nice to have". The LLM's only (optional) role is a
    one-line "why now" *timing* narration on top of the rule-computed tier, reusing the traced
    client. **Open data question:** if `observed_at` spans multiple scans, add a *trajectory*
    term (worsening posture = the strongest timing trigger); if it's a single snapshot, drop it.
    Distinct from Summary (what's wrong) and Outreach (the email) — this is the *decision* layer.
    *Effort:* Medium (SQL column + API field + a button; optional LLM narration second).

13. **Worklist scale & filtering (UI).** The worklist is capped at **100 rows** (`limit: 100`
    hard-coded in the frontend) with **no pagination**, and the only score control is a
    `min_score` floor — no max, no range, and sort is fixed (`total_score` descending). For a
    real book of thousands of accounts a rep needs to page through results and bound the score
    window. Add `offset`/cursor + `max_score` params to `/worklist` (in both `LocalRepo` and
    `SnowflakeRepo`), then a paginated list (using `facets.total`), a min–max score range
    control, and an optional sort toggle (score / tier) in the React UI. *Effort:* Medium.
