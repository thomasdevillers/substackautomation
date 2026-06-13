# ---------- Stage 1: build the React SPA ----------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build      # emits to /app/backend/static (per vite.config.js)

# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim AS runtime
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/notes.db \
    STATIC_DIR=/app/backend/static

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Bring in the built SPA from stage 1.
COPY --from=frontend /app/backend/static ./static

# Railway provides $PORT; default to 8000 locally.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
