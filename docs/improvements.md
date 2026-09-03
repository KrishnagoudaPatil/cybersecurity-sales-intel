# Improvement Backlog

Known limitations and how we'd address them, prioritised by leverage. A living list —
several items were surfaced while validating the pipeline on the real data.

## Entity resolution (highest leverage)
The biggest source of error: mapping scanned hosts to the real company that owns them.
`int_service_company` was rebuilt as a **confidence-ranked attribution waterfall** and
validated on the 100k sample — items 1–3 and 6 below are now **addressed**.

**Measured attribution coverage (100k sample), a deliberate precision-over-recall choice:**
of 99,711 services, **~10.3% are attributed** to a company (5,272 via cert, 4,960 via
reverse-DNS). The ~90% that drop out are: **30.6%** with no cert *and* no domain
(unattributable from this data), and most of the **68%** with reverse-DNS sitting on a
provider org (**54%** match an infra org pattern; most of the rest carry a cloud PTR like
`amazonaws.com` caught by `infra_domains`). The previous reverse-DNS-only model attributed
~68% — but that recall is exactly what produced the phantom mega-companies (e.g.
`incapdns.net` = 21,407 hosts). For a sales worklist, 10% *real* accounts beats 68% mostly
hosting artifacts. Items 1b, 4, and 5 below are the levers to lift recall **without**
reintroducing phantoms.

1. ✅ **Done — Resolve company from the TLS certificate.** The waterfall now uses
   `ssl.cert.subject.CN` (→ registrable domain) as the primary, highest-confidence (0.9)
   signal, trusted even on cloud/hosting IPs, and pulls the company *name* from
   `subject.O`. This recovers real tenants the old reverse-DNS logic could never find
   (e.g. `microsoft.com`, `duolingo.com`, `cam.ac.uk`, `kaseya.com` on cloud IPs).

1b. **Parse the TLS SAN, not just the CN.** Cert coverage is only 9.4% on `subject.CN`
    alone; the Subject Alternative Name lists further domains and would raise cert-based
    recall. Skipped so far because Shodan stores SAN as raw ASN.1 bytes in
    `ssl.cert.extensions[].data` — extract the DNS names with a regex. *Effort:* Medium.

2. ✅ **Done (patterns) — Auto-detect infrastructure via org instead of only a domain
   list.** The reverse-DNS signal is now distrusted when the host's `org` matches the
   `infra_org_patterns` seed (hosting/CDN/telco substrings). *Remaining upgrades:* (a) key
   off a curated **hosting-ASN list** rather than fuzzy org strings, for higher precision;
   (b) **measure false positives** — the 54% of reverse-DNS hosts on provider orgs may
   include a provider's own corporate servers (real prospects); the cert path should
   already rescue those, but confirm how many cert-less hosts on provider orgs we discard.

3. ✅ **Done — Guardrail test for implausible companies.**
   `tests/assert_company_footprint_plausible.sql` warns when a `company_domain` has
   `host_count > 150`. Turned "fails open" into "fails loud"; it currently flags the
   residual leakers (e.g. `btcentralplus.com`, `play.pl`) for triage.

4. **Passive / forward DNS enrichment.** Shodan gives reverse DNS; a passive-DNS source
   gives which domains point *to* an IP. Use it to attribute no-domain, no-cert hosts.
   *Impact:* Medium. *Effort:* Medium/High.

5. **"Unattributed exposures" bucket.** Don't discard services with findings but no
   company — keep them in a separate model for an ops view and later matching.
   *Impact:* Medium. *Effort:* Low.

6. ✅ **Done (stop-gap) — Expanded the `infra_domains` seed** with the leakers surfaced at
   100k (`incapdns.net`, `flyio.net`, `vultrusercontent.com`, `secureserver.net`,
   `linodeusercontent.com`, `bluehost.com`, `colocrossing.com`, consumer-ISP domains, …).
   Whack-a-mole by nature — superseded properly by #2's ASN approach and #6b below.

6b. **Full Public Suffix List as a seed.** `registrable_domain` uses a hand-curated
    two-level-suffix set (a PSL stand-in); loading the real PSL removes the bare-eTLD
    leakers (`ne.jp`, `net.id`, …) for good. *Effort:* Low/Medium.

6c. **Appliance / default-cert blocklist.** Some hosts present default certs whose subject
    is a vendor/placeholder (`localhost.localdomain`, `Fortinet`, `Acme Co`,
    `HTTPS Management Certificate`); reserved TLDs and placeholders are already filtered,
    but a small default-cert blocklist would catch the rest. *Effort:* Trivial.

## Signal quality
7. **CVE severity (CVSS) weighting.** Today all CVEs count equally; enrich with CVSS so a
   critical RCE outranks a low-severity issue. *Effort:* Medium.
8. **Robust header parsing.** Current missing-header checks use a lowercased key string +
   LIKE; move to structured key iteration for edge cases.
8b. **Tiny-footprint accounts score too high.** A 1-host company with a couple of CVEs can
    reach tier A because `risk_score` caps near 100 regardless of footprint size. Consider
    scaling risk by footprint/confidence, or a minimum-evidence floor, so single-host
    shells don't crowd out substantial prospects. *Effort:* Low.

## Scale & operations
9. **Load the full 74 GB**, not the sample: land in an external stage (S3) + Snowpipe,
   scale the warehouse, cluster RAW by scan date. *Effort:* Medium.
10. **Orchestrate** load -> dbt as one scheduled pipeline (dbt Cloud / Airflow) instead of
    two manual commands.
11. **Incremental models** so re-runs process only new scan dates.

## AI-native layer
12. ✅ **Done — Realign the LLM feature to the real data.** The evaluated feature is now
    service-**banner classification** (6-way taxonomy) on real Shodan banners, plus a
    findings-grounded "why-now" summary and outreach draft. The labelled eval set is 28
    hand-labelled real banners (`evals/labelled_banners.jsonl`). Remaining: grow the set to
    100+ with adversarial cases and run it against the live model (see #14).

## Product / app
13. ✅ **Done — Repoint the app to the Snowflake marts.** The API now reads the real scored
    prospects through a repository with two backends (`DATA_BACKEND`): a local `data/marts`
    snapshot by default, or live Snowflake queries. The old synthetic JSONL path is gone.

## Follow-ups
14. **Live-model eval run.** The 28-banner eval currently runs in version-aware mock mode;
    run the same harness against the live model with a key and record real numbers.
15. **Scoring weights as dbt `vars`.** The risk/fit weights in `fct_account_score.sql` are
    literals; move them to `dbt_project.yml` vars so they're tunable without editing SQL
    (also fixes the model comment that already claims they're vars). *Effort:* Trivial.
