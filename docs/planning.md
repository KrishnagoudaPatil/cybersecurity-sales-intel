# Planning — Use cases & why

## The customer we're building for
A salesperson at a **cybersecurity software vendor** selling into the ANZ mid-market.
Their daily question is not "who exists?" but **"who should I call first, and why?"**
Everything here optimises that decision.

## How B2B teams actually prospect (the research that drove the build)
Modern outbound sales runs on four moves. I built one feature for each:

| Sales motion | What reps do | Feature in this app |
|--------------|--------------|---------------------|
| **ICP definition** | Agree who is a good-fit account (industry, size, geography) | Deterministic **ICP fit score** (`scoring/icp.py`) |
| **Account scoring / prioritisation** | Rank the book so time goes to the best accounts | **Total score + A–D tiering**, sortable worklist |
| **Buying signals / intent** | Watch for events that mean "in-market now" | **Signal engine** (rule + LLM) — breach, hiring, cloud, compliance, leadership |
| **Territory / segment filtering** | Slice to my patch | **Filters**: industry, state, size band, tier, min-score |
| **Outreach** | Personalise the first touch | **On-demand "why now" + draft email** |

## Why these signals mean "needs cybersecurity"
The creative core of the task is finding cyber-intent in company data. The signals I chose:

- **Regulated industry** (finance/health/gov/critical-infra) → legal obligation to spend
  (APRA CPS 234, SOCI Act, Privacy Act, Essential Eight, PCI-DSS).
- **Breach / ransomware disclosure** → the single strongest "buy now" trigger.
- **Hiring surge** → attack surface expanding faster than controls.
- **Security-role hiring** → an actual, funded security initiative underway.
- **Cloud migration / digital transformation** → new, unfamiliar attack surface.
- **No security vendor in a mid-market firm** → an obvious capability gap.
- **Leadership change (CIO/CTO/CISO)** → budget reset, new initiatives.
- **Funding round** → ability to spend.

## Scope decisions (what I deliberately did NOT build)
- No auth / multi-tenant / CRM sync — out of scope for a prototype; noted in architecture.
- No auto-send of email — drafts are human-in-the-loop by design (see the skill guardrails).
- Synthetic dataset — the provided link 404'd; I built a schema-faithful stand-in behind a
  loader boundary so the real Firmable file swaps in with one function. This is the top
  known limitation (see how-you-build.md).
