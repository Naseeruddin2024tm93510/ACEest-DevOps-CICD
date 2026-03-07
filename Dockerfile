# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — ACEest Fitness & Gym Management
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered stdout (better for container logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup appuser

WORKDIR /app

# Install dependencies (as root, before switching user)
COPY requirements.txt .
RUN pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and test suite
COPY app.py       .
COPY test_app.py  .

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 5000

# Health check so Docker / orchestrators can probe readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# Start the Flask development server
CMD ["python", "-m", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "5000"]
