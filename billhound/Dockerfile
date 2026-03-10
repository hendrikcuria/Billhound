# ── Stage 1: Build Python dependencies ────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time system deps for asyncpg and cryptography wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install Python dependencies into a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .


# ── Stage 2: Production runtime ───────────────────────────────
FROM python:3.12-slim AS runtime

# System deps for asyncpg (libpq) and general runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Playwright system dependencies + Chromium browser
# This installs all shared libraries needed by Chromium (libglib, libnss, libatk, etc.)
RUN playwright install --with-deps chromium

WORKDIR /app

# Copy application source
COPY . .

# Create screenshot directory
RUN mkdir -p /app/data/screenshots

# Non-root user for security
RUN useradd --create-home --shell /bin/bash billhound \
    && chown -R billhound:billhound /app
USER billhound

# OAuth callback server port (also used for health checks)
EXPOSE 8080

# Health check via the /health endpoint on the OAuth callback server
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "src.main"]
