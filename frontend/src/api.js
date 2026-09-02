// Single API boundary. Dev uses the Vite proxy (/api -> :8000). For the single-origin
// build served by FastAPI, build with VITE_API_BASE="" so calls hit root paths.
const RAW = import.meta.env.VITE_API_BASE;
const BASE = RAW === undefined ? "/api" : RAW; // "" => same-origin root

async function j(path, opts) {
  const r = await fetch(BASE + path, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  health: () => j("/health"),
  facets: () => j("/facets"),
  worklist: (params) => j("/worklist?" + new URLSearchParams(params).toString()),
  company: (domain) => j(`/companies/${encodeURIComponent(domain)}`),
  summary: (domain) => j(`/companies/${encodeURIComponent(domain)}/summary`, { method: "POST" }),
  outreach: (domain) => j(`/companies/${encodeURIComponent(domain)}/outreach`, { method: "POST" }),
  cost: () => j("/cost"),
};
