import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";

const TIER_META = {
  A: { label: "A", color: "var(--tier-a)" },
  B: { label: "B", color: "var(--tier-b)" },
  C: { label: "C", color: "var(--tier-c)" },
  D: { label: "D", color: "var(--tier-d)" },
};

function TierBadge({ tier }) {
  const m = TIER_META[tier] || TIER_META.D;
  return <span className="tier" style={{ background: m.color }}>{m.label}</span>;
}

function ScoreBar({ value, kind }) {
  return (
    <div className="scorebar">
      <div className={`scorebar-fill ${kind}`} style={{ width: `${value}%` }} />
      <span className="scorebar-num">{Math.round(value)}</span>
    </div>
  );
}

function Filters({ facets, filters, setFilters }) {
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  return (
    <aside className="filters">
      <h2>Target</h2>
      <label>Industry
        <select value={filters.industry} onChange={set("industry")}>
          <option value="">All industries</option>
          {facets.industries?.map((i) => <option key={i} value={i}>{i}</option>)}
        </select>
      </label>
      <label>State
        <select value={filters.state} onChange={set("state")}>
          <option value="">All states</option>
          {facets.states?.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label>Employees
        <select value={filters.employee_band} onChange={set("employee_band")}>
          <option value="">Any size</option>
          {facets.employee_bands?.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </label>
      <label>Tier
        <select value={filters.tier} onChange={set("tier")}>
          <option value="">All tiers</option>
          {["A", "B", "C", "D"].map((t) => <option key={t} value={t}>Tier {t}</option>)}
        </select>
      </label>
      <label>Min score: <b>{filters.min_score}</b>
        <input type="range" min="0" max="100" value={filters.min_score}
          onChange={set("min_score")} />
      </label>
      <div className="tier-legend">
        {Object.entries(facets.tiers || {}).map(([t, n]) => (
          <div key={t}><TierBadge tier={t} /> {n}</div>
        ))}
      </div>
    </aside>
  );
}

function Worklist({ rows, onSelect, selectedId }) {
  return (
    <div className="worklist">
      <div className="wl-head">
        <span className="c-rank">#</span>
        <span className="c-name">Account</span>
        <span className="c-score">Score</span>
        <span className="c-sig">Signals</span>
      </div>
      {rows.map((r, i) => (
        <button key={r.company_id}
          className={`wl-row ${selectedId === r.company_id ? "sel" : ""}`}
          onClick={() => onSelect(r.company_id)}>
          <span className="c-rank">{i + 1}</span>
          <span className="c-name">
            <TierBadge tier={r.tier} /> {r.company_name}
          </span>
          <span className="c-score"><b>{Math.round(r.total_score)}</b></span>
          <span className="c-sig">
            {r.signals.slice(0, 3).map((s, k) => (
              <span key={k} className={`chip ${s.source}`}>{s.type.replace(/_/g, " ")}</span>
            ))}
            {r.signals.length > 3 && <span className="chip more">+{r.signals.length - 3}</span>}
          </span>
        </button>
      ))}
      {rows.length === 0 && <div className="empty">No accounts match these filters.</div>}
    </div>
  );
}

function Drawer({ id, onClose }) {
  const [data, setData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [outreach, setOutreach] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setData(null); setSummary(null); setOutreach(null);
    if (id) api.company(id).then(setData);
  }, [id]);

  if (!id) return null;
  const c = data?.company, s = data?.score;

  const gen = async (kind) => {
    setBusy(kind);
    try {
      if (kind === "summary") setSummary((await api.summary(id)).summary);
      else setOutreach(await api.outreach(id));
    } finally { setBusy(""); }
  };

  return (
    <div className="drawer">
      <button className="drawer-close" onClick={onClose}>×</button>
      {!data ? <div className="loading">Loading…</div> : (
        <>
          <div className="drawer-head">
            <TierBadge tier={s.tier} />
            <h2>{c.company_name}</h2>
          </div>
          <div className="firmo">
            <span>{c.industry}</span><span>{c.employee_count} staff</span>
            <span>{c.city}, {c.state}</span><span>${(c.annual_revenue_aud/1e6).toFixed(1)}M</span>
            <span>ABN {c.abn}</span><span>Est. {c.founded_year}</span>
          </div>

          <div className="score-grid">
            <div><label>ICP fit</label><ScoreBar value={s.icp_fit} kind="fit" /></div>
            <div><label>Intent</label><ScoreBar value={s.intent_score} kind="intent" /></div>
            <div><label>Total</label><ScoreBar value={s.total_score} kind="total" /></div>
          </div>

          <h3>Buying signals</h3>
          <div className="signals">
            {s.signals.length === 0 && <div className="muted">No strong signals.</div>}
            {s.signals.map((sig, k) => (
              <div key={k} className="signal">
                <span className={`chip ${sig.source}`}>{sig.source}</span>
                <div>
                  <b>{sig.type.replace(/_/g, " ")}</b>
                  <p>{sig.evidence}</p>
                </div>
              </div>
            ))}
          </div>

          <h3>Score breakdown</h3>
          <table className="breakdown">
            <tbody>
              {s.breakdown.map((b, k) => (
                <tr key={k}><td>{b.component.replace(/_/g, " ")}</td>
                  <td className="pts">+{b.points}</td><td className="detail">{b.detail}</td></tr>
              ))}
            </tbody>
          </table>

          <h3>Recent events (raw)</h3>
          <ul className="events">{c.recent_events.map((e, k) => <li key={k}>{e}</li>)}</ul>

          <div className="actions">
            <button disabled={busy} onClick={() => gen("summary")}>
              {busy === "summary" ? "Generating…" : "Why now →"}
            </button>
            <button disabled={busy} onClick={() => gen("outreach")}>
              {busy === "outreach" ? "Drafting…" : "Draft outreach ✉"}
            </button>
          </div>
          {summary && <div className="ai-out"><label>Why now</label><p>{summary}</p></div>}
          {outreach && (
            <div className="ai-out email">
              <label>Draft email · {outreach.model}</label>
              <p className="subj"><b>Subject:</b> {outreach.subject}</p>
              <pre>{outreach.body}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function App() {
  const [facets, setFacets] = useState({});
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [health, setHealth] = useState(null);
  const [cost, setCost] = useState(null);
  const [filters, setFilters] = useState({
    industry: "", state: "", tier: "", employee_band: "", min_score: 0,
  });

  useEffect(() => {
    api.facets().then(setFacets);
    api.health().then(setHealth);
    api.cost().then(setCost);
  }, []);

  const load = useCallback(() => {
    const p = { limit: 100 };
    Object.entries(filters).forEach(([k, v]) => { if (v) p[k] = v; });
    api.worklist(p).then(setRows);
  }, [filters]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">🛡️ CyberShield <span>Sales Intelligence</span></div>
        <div className="meta">
          {health && <span className={`pill ${health.llm_mode}`}>LLM: {health.llm_mode}</span>}
          {cost && <span className="pill cost">${cost.total_cost_usd?.toFixed(3)} · {cost.calls} calls</span>}
          <span className="pill">{facets.total} accounts</span>
        </div>
      </header>
      <div className="body">
        <Filters facets={facets} filters={filters} setFilters={setFilters} />
        <main>
          <div className="main-head">
            <h1>Prospect worklist</h1>
            <p>{rows.length} accounts, ranked by likelihood to buy cybersecurity software.</p>
          </div>
          <Worklist rows={rows} onSelect={setSelected} selectedId={selected} />
        </main>
        <Drawer id={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
