# ---- stage 1: build the React SPA ----
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- stage 2: python backend serving the SPA ----
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY prompts/ ./prompts/
COPY data/ ./data/
COPY --from=web /web/dist ./frontend/dist
ENV PYTHONPATH=/app/backend
# The app serves the committed data/marts/*.json snapshot (COPY'd above), so the
# container boots ready with no data-generation step. Cloud Run injects $PORT (8080).
EXPOSE 8080
CMD ["sh", "-c", "cd backend && uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
