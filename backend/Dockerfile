# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install CPU-only torch first (large wheel, separate layer for cache efficiency).
# Pinned to match requirements.lock so the locked install below is satisfied
# without needing the PyTorch index.
RUN pip install --no-cache-dir torch==2.12.0+cpu --index-url https://download.pytorch.org/whl/cpu

# Install from the fully-pinned lock file for deterministic, conflict-free builds
# (no dependency backtracking). requirements.txt is kept as the human-readable
# source of intent; regenerate the lock with:  pip freeze > requirements.lock
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Download spaCy NER model used by the ingestion pipeline
RUN python -m spacy download en_core_web_sm

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create a non-root user WITH a home dir (the HuggingFace/sentence-transformers
# cache needs a writable HOME, else the embedding model fails to load).
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

# Cache locations for the embedding model — point at the app user's home.
ENV HOME=/home/app
ENV HF_HOME=/home/app/.cache/huggingface

# Copy installed packages and model from the builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install curl for the HEALTHCHECK (slim image doesn't include it)
RUN apt-get update -qq && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

USER app

# Bake the embedding model into the image so startup is fast and works offline
# (no ~1.3GB re-download on every container start). Done BEFORE copying app code
# so this expensive layer stays cached across code changes.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"

# App code last — only this layer rebuilds on a code change.
COPY --chown=app:app . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
