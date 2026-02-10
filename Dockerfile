# ============================================================================
# Hebbian Mind Enterprise Dockerfile
# Neural Graph Memory System with Hebbian Learning
# ============================================================================
# Author: CIPS LLC
# License: Proprietary - CIPS LLC
# ============================================================================

# ===========================================================================
# Stage 1: Builder - Install dependencies and prepare application
# ===========================================================================
FROM python:3.12-slim AS builder

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Copy project files
COPY pyproject.toml /build/
COPY README.md /build/

# Copy source code (must exist before editable install)
COPY src/ /build/src/

# Install the package (not editable - needed for multi-stage builds)
RUN pip install --no-cache-dir /build/

# ===========================================================================
# Stage 2: Runtime - Lean production image
# ===========================================================================
FROM python:3.12-slim AS runtime

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 hebbian \
    && useradd --uid 1000 --gid hebbian --shell /bin/bash --create-home hebbian

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --from=builder /build/src /app/src
COPY --from=builder /build/pyproject.toml /app/
COPY --from=builder /build/README.md /app/

# Create directories for persistence and RAM disk
RUN mkdir -p /data/hebbian_mind/disk /data/hebbian_mind/nodes \
    && chown -R hebbian:hebbian /app /data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Application configuration
    HEBBIAN_MIND_BASE_DIR=/data/hebbian_mind \
    HEBBIAN_MIND_RAM_DISK=false \
    HEBBIAN_MIND_RAM_DIR=/app/ramdisk \
    HEBBIAN_MIND_THRESHOLD=0.3 \
    HEBBIAN_MIND_EDGE_FACTOR=1.0 \
    HEBBIAN_MIND_MAX_WEIGHT=10.0 \
    HEBBIAN_MIND_LOG_LEVEL=INFO \
    # FAISS integration (disabled by default)
    HEBBIAN_MIND_FAISS_ENABLED=false \
    HEBBIAN_MIND_FAISS_HOST=localhost \
    HEBBIAN_MIND_FAISS_PORT=9998 \
    # PRECOG integration (disabled by default)
    HEBBIAN_MIND_PRECOG_ENABLED=false \
    HEBBIAN_MIND_PRECOG_PATH="" \
    # Temporal decay (enabled by default)
    HEBBIAN_MIND_DECAY_ENABLED=true \
    HEBBIAN_MIND_DECAY_BASE_RATE=0.01 \
    HEBBIAN_MIND_DECAY_THRESHOLD=0.1 \
    HEBBIAN_MIND_DECAY_IMMORTAL_THRESHOLD=0.9 \
    HEBBIAN_MIND_DECAY_SWEEP_INTERVAL=60 \
    HEBBIAN_MIND_EDGE_DECAY_ENABLED=true \
    HEBBIAN_MIND_EDGE_DECAY_RATE=0.005 \
    HEBBIAN_MIND_EDGE_DECAY_MIN_WEIGHT=0.1

# No port exposure - MCP uses stdio by default
# For future HTTP/socket API, expose port here

# Health check - verify database is accessible
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sqlite3; from pathlib import Path; db_path = Path('/data/hebbian_mind/disk/hebbian_mind.db'); exit(0 if db_path.parent.exists() else 1)" || exit 1

# Switch to non-root user
USER hebbian

# Labels for container metadata
LABEL org.opencontainers.image.title="hebbian-mind-enterprise" \
      org.opencontainers.image.description="Neural Graph Memory System with Hebbian Learning" \
      org.opencontainers.image.vendor="CIPS LLC" \
      org.opencontainers.image.version="2.2.0" \
      org.opencontainers.image.licenses="Proprietary"

# Entry point - run the MCP server in standalone mode for Docker
# Standalone mode keeps container alive for health checks
# MCP clients connect via SSE bridge or docker exec with proper stdio
CMD ["python", "-m", "hebbian_mind.server", "--standalone"]
