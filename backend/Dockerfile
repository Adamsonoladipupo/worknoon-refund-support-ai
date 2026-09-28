# ─────────────────────────────────────────────────────────────────────────────
# Worknoon Refund System — Backend Image
# ─────────────────────────────────────────────────────────────────────────────
# Single stage (assessment scope). Uses the official slim Python image.
# Runs Alembic migrations + seed data, then starts uvicorn.
#
# Build args:
#   (none — all config is supplied at runtime via environment variables)
#
# Runtime env vars required:
#   DATABASE_URL   e.g. postgresql+psycopg://user:pass@db:5432/dbname
#   AI_API_KEY     Google Gemini API key
#   AI_MODEL       e.g. gemini-2.0-flash  (default in Settings)
#   APP_ENV        development | production
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Don't write .pyc files into the image; flush stdout/stderr immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps needed by psycopg (libpq).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer-cache friendly).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY . .

# Expose the uvicorn port.
EXPOSE 8000

# Entrypoint: run migrations, seed data, then start the server.
# We use `sh -c` so the CMD below can still pass arguments if needed.
CMD ["sh", "-c", \
     "alembic upgrade head && python -m scripts.seed && \
      uvicorn app.main:app --host 0.0.0.0 --port 8000"]
