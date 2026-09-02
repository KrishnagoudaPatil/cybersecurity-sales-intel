import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";

const TIER_COLOR = { A: "var(--tier-a)", B: "var(--tier-b)", C: "var(--tier-c)", D: "var(--tier-d)" };
const TierBadge = ({ tier }) => (
  <span className="tier" style={{ background: TIER_COLOR[tier] || TIER_COLOR.D }}>{tier}</span>
);

// Build finding chips from a company's aggregate counts.
function findingChips(c) {
  const out = [];
  if (c.total_cves > 0) out.push({ t: `${c.total_cves} CVE${c.total_cves > 1 ? "s" : ""}`, k: "crit" });
  if (c.exposed_db_services > 0) out.push({ t: "exposed DB", k: "crit" });
  if (c.exposed_remote_services > 0) out.push({ t: "remote access", k: "warn" });
  if (c.eol_services > 0) out.push({ t: "EOL", k: "warn" });
  if (c.weak_tls_services > 0) out.push({ t: "weak TLS", k: "warn" });
  if (c.self_signed_services > 0) out.push({ t: "self-signed", k: "" });
  if ((c.missing_header_ratio || 0) >= 0.5) out.push({ t: "missing hdrs", k: "" });
  return out;
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
      <label>Country
        <select value={filters.country} onChange={set("country")}>
          <option value="">All countries</option>
          {facets.countries?.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </label>
      <label>Company size
        <select value={filters.size_band} onChange={set("size_band")}>
          <option value="">Any size</option>
          {facets.size_bands?.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </label>
      <label>Tier
        <select value={filters.tier} onChange={set("tier")}>
          <option value="">All tiers</option>
          {["A", "B", "C", "D"].map((t) => <option key={t} value={t}>Tier {t}</option>)}
        </select>
      </label>
      <label>Min score: <b>{filters.min_score}</b>
        <input type="range" min="0" max="100" value={filters.min_score} onChange={set("min_score")} />
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
        <span className="c-rank">#</span><span className="c-name">Company</span>
        <span className="c-score">Score</span><span className="c-sig">Exposure</span>
      </div>
      {rows.map((r, i) => (
        <button key={r.company_domain}
          className={`wl-row ${selectedId === r.company_domain ? "sel" : ""}`}
          onClick={() => onSelect(r.company_domain)}>
          <span className="c-rank">{i + 1}</span>
          <span className="c-name"><TierBadge tier={r.tier} /> {r.company_domain}</span>
          <span className="c-score"><b>{Math.round(r.total_score)}</b></span>
          <span className="c-sig">
            {findingChips(r).slice(0, 4).map((c, k) => (
              <span key={k} className={`chip ${c.k}`}>{c.t}</span>
            ))}
          </span>
        </button>
      ))}
      {rows.length === 0 && <div className="empty">No companies match these filters.</div>}
    </div>
  );
}

function svcChips(s) {
  const out = [];
  if (s.cve_count > 0) out.push({ t: `${s.cve_count} CVE`, k: "crit" });
  if (s.exposed_database) out.push({ t: "DB", k: "crit" });
  if (s.exposed_remote_access) out.push({ t: "remote", k: "warn" });
  if (s.is_eol) out.push({ t: "EOL", k: "warn" });
  if (s.weak_tls) out.push({ t: "weak TLS", k: "warn" });
  if (s.self_signed) out.push({ t: "self-signed", k: "" });
  return out;
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
  const c = data?.company, services = data?.services || [];

  const gen = async (kind) => {
    setBusy(kind);
    try {
      if (kind === "summary") setSummary((await api.summary(id)).summary);
      else setOutreach(await api.outreach(id));
    } finally { setBusy(""); }
  };

  const FINDINGS = [
    ["total_cves", "Known CVEs"], ["exposed_db_services", "Exposed databases"],
    ["exposed_remote_services", "Exposed remote access"], ["eol_services", "End-of-life software"],
    ["self_signed_services", "Self-signed certs"], ["weak_tls_services", "Weak TLS"],
    ["expired_cert_services", "Expired certs"],
  ];

  return (
    <div className="drawer">
      <button className="drawer-close" onClick={onClose}>×</button>
      {!data ? <div className="loading">Loading…</div> : (
        <>
          <div className="drawer-head"><TierBadge tier={c.tier} /><h2>{c.company_domain}</h2></div>
          <div className="firmo">
            <span>{c.primary_country}</span><span>{c.size_band}</span>
            <span>{c.host_count} hosts</span><span>{c.service_count} services</span>
            <span>{c.distinct_ports} ports</span><span>host: {c.primary_hosting_org}</span>
          </div>

          <div className="score-grid">
            <div><label>Risk</label><ScoreBar value={c.risk_score} kind="intent" /></div>
            <div><label>Fit</label><ScoreBar value={c.fit_score} kind="fit" /></div>
            <div><label>Total</label><ScoreBar value={c.total_score} kind="total" /></div>
          </div>

          <h3>Exposure summary</h3>
          <div className="findings">
            {FINDINGS.filter(([k]) => (c[k] || 0) > 0).map(([k, label]) => (
              <div key={k} className="finding"><b>{c[k]}</b> {label}</div>
            ))}
            {(c.missing_header_ratio || 0) > 0 &&
              <div className="finding"><b>{Math.round(c.missing_header_ratio * 100)}%</b> HTTP security headers missing</div>}
            {findingChips(c).length === 0 && <div className="muted">No significant exposure.</div>}
          </div>

          <h3>Exposed services ({services.length})</h3>
          <div className="svc-list">
            {services.map((s, k) => (
              <div key={k} className="svc">
                <span className="svc-ipp">{s.ip}:{s.port}</span>
                <span className="svc-prod">{s.product || "—"}</span>
                <span className="svc-chips">{svcChips(s).map((x, i) =>
                  <span key={i} className={`chip ${x.k}`}>{x.t}</span>)}</span>
              </div>
            ))}
          </div>

          <div className="actions">
            <button disabled={busy} onClick={() => gen("summary")}>
              {busy === "summary" ? "Generating…" : "Why now →"}</button>
            <button disabled={busy} onClick={() => gen("outreach")}>
              {busy === "outreach" ? "Drafting…" : "Draft outreach ✉"}</button>
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
  const [filters, setFilters] = useState({ country: "", size_band: "", tier: "", min_score: 0 });

  useEffect(() => {
    api.facets().then(setFacets); api.health().then(setHealth); api.cost().then(setCost);
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
          {health && <span className="pill">data: {health.data_backend}</span>}
          {health && <span className={`pill ${health.llm_mode}`}>LLM: {health.llm_mode}</span>}
          {cost && <span className="pill cost">${cost.total_cost_usd?.toFixed(3)} · {cost.calls} calls</span>}
          {facets.total != null && <span className="pill">{facets.total} companies</span>}
        </div>
      </header>
      <div className="body">
        <Filters facets={facets} filters={filters} setFilters={setFilters} />
        <main>
          <div className="main-head">
            <h1>Prospect worklist</h1>
            <p>{rows.length} companies, ranked by observed security risk × market fit.</p>
          </div>
          <Worklist rows={rows} onSelect={setSelected} selectedId={selected} />
        </main>
        <Drawer id={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
