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
# Build the dataset at image build time so the container boots ready.
RUN cd backend && python -m app.data_gen --n 600
EXPOSE 8000
CMD ["sh", "-c", "cd backend && uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
