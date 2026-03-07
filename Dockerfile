# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — ACEest Fitness & Gym Management
# Multi-stage, non-root, minimal attack surface
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build / dependency installation ──────────────────────────────────
FROM python:3.12-slim AS builder

# Prevent .pyc files and enable unbuffered stdout (better for container logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install dependencies into an isolated prefix so we can copy them cleanly
COPY requirements.txt .
RUN pip install --upgrade pip --quiet && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source and test suite
COPY app.py           .
COPY requirements.txt .
COPY test_app.py      .

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 5000

# Health check so Docker / orchestrators can probe readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# Run the application with Gunicorn (production-grade WSGI server)
# Falls back gracefully if gunicorn is absent (development mode)
CMD ["python", "-m", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "5000"]
