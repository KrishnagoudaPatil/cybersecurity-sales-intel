# Deploy

The app is **one container**: the Dockerfile builds the React SPA and serves it from the
FastAPI backend, so you get a **single URL** (UI + API on one origin, no CORS). It boots
ready — it serves the committed `data/marts/*.json` snapshot, with no data-generation step.
With no LLM key it runs in deterministic **mock mode** (evals, traces, cost accounting all
still work); set a key to use live models. The container listens on `$PORT` (default 8080).

## LLM keys (optional — omit for mock mode)
- `GEMINI_API_KEY` — free-tier Google AI Studio key; the provider auto-selects Gemini.
- `ANTHROPIC_API_KEY` — Claude; takes precedence if both are set.
- `LLM_PROVIDER=gemini|anthropic|mock` — force one explicitly.

## Cloud Run (one URL, scales to zero, ~$0 at demo traffic)
Prereqs: a GCP project with **billing enabled** (required even for the free tier) and the
`gcloud` CLI (`gcloud init` to log in and pick the project).

```bash
# one-time: enable the build + run APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# build (via Cloud Build) + deploy; prints the public HTTPS URL
gcloud run deploy cybersecurity-sales-intel \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars DATA_BACKEND=local
```

`--source .` hands the repo to Cloud Build, which builds the Dockerfile and deploys the
image. Redeploy = rerun the same command. Cloud Run scales to zero when idle, so there is
no cost between demos (cold start ~1–3s on the first hit).

Live LLM: rather than putting the key in plain env, store it in Secret Manager and mount it:
```bash
echo -n "<your-gemini-key>" | gcloud secrets create gemini-api-key --data-file=-
gcloud run deploy cybersecurity-sales-intel --source . --region asia-south1 \
  --allow-unauthenticated --set-env-vars DATA_BACKEND=local \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

## Local (one container)
```bash
docker build -t firmable-si .
docker run -p 8080:8080 -e GEMINI_API_KEY=$GEMINI_API_KEY firmable-si
# open http://localhost:8080   (omit -e to run in mock mode)
```
