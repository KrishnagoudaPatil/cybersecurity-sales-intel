# Improvement Backlog

Known limitations and how we'd address them, prioritised by leverage. A living list —
several items were surfaced while validating the pipeline on the real data.

## Entity resolution (highest leverage)
The biggest source of error: mapping scanned hosts to the real company that owns them.

1. **Resolve company from the TLS certificate.**
   - *Problem:* 358/998 sample services have no domain at all (no reverse-DNS / PTR
     record), so they drop out of the company marts — even though these bare hosts
     (databases, IoT, admin panels) are often the most security-exposed prospects.
   - *Idea:* When `domains` is empty, read the domain off the TLS certificate — the `ssl`
     object's certificate subject CN / SAN frequently names the real domain even when
     reverse DNS does not (e.g. `CN=admin.acme.com`). Use it as a fallback company key.
   - *Impact:* High — recovers high-risk hosts we currently discard. *Effort:* Medium.

2. **Auto-detect infrastructure via ASN/org instead of a hand-kept domain list.**
   - *Problem:* `infra_domains` is a manual seed; a missing entry silently creates a fake
     company (e.g. `incapdns.net` = 244 hosts, `myftpupload.com`, `vultrusercontent.com`
     slipped through). It "fails open".
   - *Idea:* The data already identifies the host in `org`/`isp`/`asn` (few, stable
     providers). Maintain a hosting ASN/org list and flag infra from that, plus a
     public-suffix list to extract true registrable domains. Keep the domain as the
     company key, but derive the infra filter from the data.
   - *Impact:* High. *Effort:* Medium.

3. **Guardrail test for implausible companies.**
   - Add a dbt test that fails when a `company_domain` has an improbable footprint for one
     company (host_count above a threshold, spans many ASNs, or `primary_hosting_org`
     matches a provider pattern). New infra domains surface as a failing test instead of
     quietly polluting the marts. *Impact:* Medium. *Effort:* Low.

4. **Passive / forward DNS enrichment.** Shodan gives reverse DNS; a passive-DNS source
   gives which domains point *to* an IP. Use it to attribute no-domain hosts.
   *Impact:* Medium. *Effort:* Medium/High.

5. **"Unattributed exposures" bucket.** Don't discard services with findings but no
   company — keep them in a separate model for an ops view and later matching.
   *Impact:* Medium. *Effort:* Low.

6. **Expand the `infra_domains` seed** with known gaps (`vultrusercontent.com`,
   `myftpupload.com`, `secureserver.net`, `linodeusercontent.com`, `ngrok.io`,
   `incapdns.net`, `flyio.net`, …). Quick stop-gap until #2 lands. *Effort:* Trivial.

## Signal quality
7. **CVE severity (CVSS) weighting.** Today all CVEs count equally; enrich with CVSS so a
   critical RCE outranks a low-severity issue. *Effort:* Medium.
8. **Robust header parsing.** Current missing-header checks use a lowercased key string +
   LIKE; move to structured key iteration for edge cases.

## Scale & operations
9. **Load the full 74 GB**, not the sample: land in an external stage (S3) + Snowpipe,
   scale the warehouse, cluster RAW by scan date. *Effort:* Medium.
10. **Orchestrate** load -> dbt as one scheduled pipeline (dbt Cloud / Airflow) instead of
    two manual commands.
11. **Incremental models** so re-runs process only new scan dates.

## AI-native layer
12. **Realign the LLM feature to the real data.** The synthetic signal-classification eval
    is now orphaned; repoint the LLM to a "why-now" security-risk narrative + outreach
    grounded in real findings, with a fresh labelled eval set.

## Product / app
13. **Repoint the app to the Snowflake marts** (currently reads the old synthetic JSONL)
    so the UI shows real scored prospects.
