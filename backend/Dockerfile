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

COPY . .

EXPOSE 8000

# Run migrations and seed data before starting the server.
CMD ["sh", "-c", \
     "alembic upgrade head && python -m scripts.seed && \
      uvicorn app.main:app --host 0.0.0.0 --port 8000"]
