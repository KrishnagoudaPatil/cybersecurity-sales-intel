# Deploy

The app is one container: the Dockerfile builds the React SPA and serves it from the
FastAPI backend, so you get a **single URL**. Runs in mock mode with no secrets; set
`ANTHROPIC_API_KEY` to use live models.

## Local (one container)
```bash
docker build -t firmable-si .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY firmable-si
# open http://localhost:8000
```

## Fly.io (one URL, free-ish)
```bash
fly launch --dockerfile Dockerfile --now
fly secrets set ANTHROPIC_API_KEY=sk-ant-...   # optional; omit to run in mock mode
```

## Render / Railway
Point a new Web Service at this repo, environment = Docker. Set `ANTHROPIC_API_KEY`
(optional). Render provides `$PORT`, which the CMD already honours.

## Split deploy (Vercel + Render), if preferred
- Backend: deploy `backend/` (or the Docker image) to Render; note its URL.
- Frontend: deploy `frontend/` to Vercel with `VITE_API_BASE=https://<backend-url>`.
