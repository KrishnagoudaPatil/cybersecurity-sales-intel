# Planning — Use cases & why

## The customer we're building for
A salesperson at a **cybersecurity software vendor**. Their daily question is not
"who exists?" but **"who should I call first, and why?"** Everything here optimises that
decision — and grounds it in evidence a rep can defend on the call.

## Why this data answers the question
The provided dataset is **Shodan internet-scan data**: one record per service observed on
one `IP:port`, carrying the software fingerprint, TLS/HTTP details, and known CVEs for
internet-facing hosts. That is close to ideal for a cybersecurity vendor, because a
company's *observed attack surface is its buying intent*. We don't infer that a bank
"probably" needs security software from its industry code; we observe that a specific
company is running end-of-life software, exposing a database, or carrying 16 known CVEs —
and rank it on that evidence. The pitch writes itself: "we scanned your public footprint
and here is what an attacker sees."

## How B2B teams prospect, mapped to features
Modern outbound runs on four moves. Each maps to something concrete in the build:

| Sales motion | What reps do | Feature in this app |
|--------------|--------------|---------------------|
| **ICP / fit definition** | Agree who is a good-fit account (geo, size) | Deterministic **fit score** in `FCT_ACCOUNT_SCORE` (target geo + size proxy) |
| **Account scoring / prioritisation** | Rank the book so time goes to the best accounts | **Risk + fit → total score + A–D tier**, sortable worklist |
| **Buying signals / intent** | Watch for evidence that means "in-market now" | **Per-service security findings** (CVEs, exposed DB/RDP, EOL, weak TLS, header hygiene) computed in dbt |
| **Territory / segment filtering** | Slice to my patch | **Filters**: country, size band, tier, min-score |
| **Outreach** | Personalise the first touch | **On-demand "why now" summary + draft email** grounded in the real findings |

## Why these signals mean "needs cybersecurity"
The creative core is choosing which observable facts constitute demonstrable need. The
signals, all derived deterministically in SQL (`int_service_signals.sql`) and weighted in
`fct_account_score.sql`:

- **Known CVEs** (from Shodan's `vulns` + `opts.vulns`) → the strongest, most concrete
  evidence: publicly-known, exploitable weaknesses the company is currently exposing.
- **Internet-exposed database** (Mongo/Redis/Elastic/MySQL/… on a public port) → a classic
  breach vector; a high-signal, easy-to-explain finding.
- **Exposed remote access** (RDP/telnet/VNC/FTP) → attackable management surface.
- **End-of-life software** → unpatched by definition; no vendor fixes coming.
- **Weak/legacy TLS** (TLSv1/1.1, SSLv2/3) and **expired / self-signed certs** → poor
  transport hygiene, often a proxy for weak security operations.
- **Missing HTTP security headers** (HSTS/CSP/X-Frame-Options/X-Content-Type-Options) →
  low-effort hardening left undone; a cheap conversation-opener.

Fit then narrows the ranked list to the vendor's addressable market (target geography +
a company-size proxy from the host footprint), and the blended `total_score` (0.6 × risk +
0.4 × fit) puts *needs-it-now, and-we-can-sell-to-them* accounts at the top.

## Scope decisions (what I deliberately did NOT build)
- **No auth / multi-tenant / CRM sync** — out of scope for a prototype; noted in
  architecture.
- **No auto-send of email** — drafts are human-in-the-loop by design (see the skill
  guardrails).
- **Sample, not the full 74 GB** — a 1k-record sample is loaded end-to-end; the same path
  (external stage + Snowpipe, warehouse scale-up) handles the full file. Landing the full
  export is item #9 in [`improvements.md`](improvements.md).
- **Entity resolution via domains** — hosts are attributed to a company by their
  registrable domain, excluding hosting/CDN infrastructure. This is the largest source of
  error and the top item in the improvement backlog (TLS-certificate and ASN/org-based
  resolution).
