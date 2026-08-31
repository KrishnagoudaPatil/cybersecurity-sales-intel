# How I Built This

## Dev loop
I built this in a single **Claude Code** session, working the way I'd run a real
sprint: I owned the decisions, the agent owned the typing. My loop was:

1. **Frame the problem first.** Before any code, I had the agent pull the task and
   research how Firmable's own product thinks about prospecting (ICP, buying signals,
   intent) so the build mirrored real sales motions rather than my assumptions.
2. **Design the seams, then fill them.** I fixed the architecture up front — a loader
   boundary for data, a single traced LLM client, a rule-vs-LLM split — and only then
   generated implementation. Getting the seams right is what kept the agent productive.
3. **Vertical slice, verified at each step.** Data generator → deterministic scoring →
   LLM layer → evals → API → UI. After each layer I ran it (a smoke test, the eval
   harness, live `curl`, a browser screenshot) before moving on, so nothing was
   "written but unproven".
4. **Decisions to me, execution to the agent.** Where to draw the rule/LLM line, which
   signals mean "needs cybersecurity", how to weight the score, what the cost ceiling
   should be — I made those. The agent scaffolded, wrote boilerplate, and wired it up.

## Where AI saved the most time
- **Scaffolding & boilerplate**: the FastAPI surface, Pydantic models, the React
  worklist/drawer, and the CSS — hours of typing collapsed into minutes.
- **The synthetic dataset**: generating a schema-faithful ANZ book with realistic,
  messy free-text events (so the LLM had something real to classify) was a huge
  accelerator versus hand-building fixtures.
- **The eval + tracing harness**: metric plumbing (precision/recall/F1, JSONL trace
  schema, cost aggregation) is exactly the tedious-but-important code AI is great at.

## Where it cost more than doing it by hand
- **A bleeding-edge runtime**: the machine had Python 3.14, which had no prebuilt wheels
  for the pinned `pydantic-core`/`tiktoken`; the agent burned a cycle on a failed build
  before I had it loosen pins and drop `tiktoken` for a tiny hand-rolled token estimator.
  A human would have reached for a known-good Python immediately.
- **A subtle correctness trap it didn't catch on its own**: in mock mode the classifier
  ignored the prompt version, so v1 and v2 scored identically — which would have made the
  whole "v2 is +39 points" story meaningless. I had to spot that and direct a fix
  (a version-aware mock). AI will happily produce a green eval that proves nothing.
- **Browser-driven UI verification** was flakier than just reading the code and hitting
  the API directly.

## One known weakness I'd flag to a teammate
**The eval numbers are honest but not yet a live-model measurement.** With no API key the
classifier runs in a deterministic mock that *simulates* each prompt version's behaviour,
so 57%→96% is a faithful story of the prompt design, not a benchmark of Claude on this
task. Before trusting it in production I'd: (1) run the same harness against the live model
with a key, (2) grow the labelled set from 28 to 100+ with adversarial/ambiguous cases,
and (3) check confidence calibration. The second thing I'd flag is that the dataset is
synthetic — the real Firmable schema will differ, and while the loader isolates that swap,
the signal extractors will need remapping to the real column names.
