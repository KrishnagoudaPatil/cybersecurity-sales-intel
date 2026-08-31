// Single API boundary. Dev uses the Vite proxy (/api -> :8000); prod uses VITE_API_BASE.
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function j(path, opts) {
  const r = await fetch(BASE + path, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  health: () => j("/health"),
  facets: () => j("/facets"),
  worklist: (params) => j("/worklist?" + new URLSearchParams(params).toString()),
  company: (id) => j(`/companies/${id}`),
  summary: (id) => j(`/companies/${id}/summary`, { method: "POST" }),
  outreach: (id) => j(`/companies/${id}/outreach`, { method: "POST" }),
  cost: () => j("/cost"),
};
