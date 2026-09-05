# How I Built This

## Dev loop
I built this in **Claude Code**, working the way I'd run a real sprint: I owned the
decisions, the agent owned the typing. My loop was:

1. **Frame the problem first.** Before any code, I had the agent pull the task and research
   how B2B teams actually prospect (ICP, buying signals, intent) so the build mirrored real
   sales motions rather than my assumptions.
2. **Let the data redefine the problem.** The build started on a schema-faithful synthetic
   ANZ firmographics stand-in (the dataset link 404'd initially). When the **real file
   arrived — 74 GB of Shodan internet-scan data, not firmographics** — I stopped and
   re-derived the whole premise from the actual records: prospects are companies with
   *observed* attack surface, and the signals are real CVEs, exposed databases, EOL
   software and TLS/header hygiene. Reading the first lines of the real data before writing
   any transform was the highest-leverage decision in the project.
3. **Move the heavy lifting into the warehouse.** Because the role is Snowflake-heavy and
   the file is 74 GB, I chose **ELT**: land the raw JSON as `VARIANT` in Snowflake and
   transform with **dbt** (staging → intermediate → marts). I was new to both, so I worked
   through each layer deliberately — why staging exists, what a VARIANT is, why entity
   resolution needs its own model — rather than accepting generated SQL I couldn't defend.
4. **Design the seams, then fill them.** A loader boundary for ingestion, a single traced
   LLM client, a repository interface with swappable local/Snowflake backends, and a strict
   rule-vs-LLM split. Getting the seams right is what kept the agent productive.
5. **Vertical slice, verified at each step.** Load → dbt models → marts → export → API → UI.
   After each layer I ran it (a `dbt build`, the eval harness, live `curl`, a browser check)
   before moving on, so nothing was "written but unproven".

## Where AI saved the most time
- **Warehouse & dbt scaffolding**: the loader (PUT/COPY INTO into a VARIANT table), the dbt
  project layout, `LATERAL FLATTEN` over semi-structured arrays, the anti-join for infra
  exclusion, and the ROW_NUMBER dedup — a lot of Snowflake-specific SQL I could learn from
  and adapt rather than write cold.
- **App scaffolding & boilerplate**: the FastAPI surface, the repository split, the React
  worklist/drawer, and the CSS — hours of typing collapsed into minutes.
- **The eval + tracing harness**: metric plumbing (precision/recall/F1, the JSONL trace
  schema, cost aggregation) is exactly the tedious-but-important code AI is great at.

## Where it cost more than doing it by hand
- **A three-valued-logic bug the agent wrote and I caught in review.** The honeypot filter
  `NOT array_contains('honeypot', tags)` silently dropped every row with *no* tags, because
  `ARRAY_CONTAINS` returns `NULL` on a null array and `NOT NULL` is `NULL`, which a `WHERE`
  treats as false. It cost ~265 rows and ~60 companies before I spotted the count was wrong
  and directed the `COALESCE(...,false)` fix. AI writes plausible SQL that is subtly wrong on
  NULL semantics.
- **A stale-knowledge detour on the runtime.** The machine runs Python 3.14, and I assumed
  `snowflake-connector-python` and `dbt` had no 3.14 wheels, so I split the Snowflake work
  into a separate 3.12 `.venv-snow`. That assumption was wrong — both install and run fine
  on 3.14 (verified with a live connector query and `dbt --version`). The lesson: check
  compatibility empirically instead of trusting training-cutoff knowledge. The `.venv-snow`
  still works but is now a historical artifact, not a requirement — one 3.14 venv does the
  app *and* the pipeline.
- **MFA friction.** Password + TOTP wouldn't cache across the loader and dbt processes, so I
  switched to **key-pair auth** — the right call for headless/CI runs, but a detour.
- **A correctness trap in the eval itself.** In mock mode the classifier initially ignored
  the prompt version, so v1 and v2 scored identically — which would have made the whole
  "v2 is better" story meaningless. I had to spot that and direct a version-aware mock. AI
  will happily produce a green eval that proves nothing.

## One known weakness I'd flag to a teammate
**Entity resolution is the pipeline's soft spot, and I'd say so on the call.** Hosts are
attributed to a company by their registrable domain, excluding a hand-kept seed of
hosting/CDN domains. Two consequences: services with *no* domain (often the most exposed —
bare databases, admin panels) drop out entirely, and a hosting domain missing from the seed
can silently create a phantom "company" with hundreds of unrelated hosts (it "fails open").
The fixes are concrete and prioritised in [`improvements.md`](improvements.md): resolve the
company from the **TLS certificate** subject/SAN when there's no domain, and derive the
infra filter from **ASN/org** in the data instead of a manual list, with a dbt guardrail
test that fails on implausible footprints.

**The eval numbers are honest but not yet a live-model measurement.** With no API key the
classifier runs in a deterministic, version-aware mock that *simulates* each prompt version,
so 50% → 100% is a faithful story of the prompt design, not a benchmark of Claude on this
task. Before trusting it in production I'd run the same harness against the live model, grow
the labelled set from 28 to 100+ with adversarial/ambiguous banners, and check confidence
calibration.
