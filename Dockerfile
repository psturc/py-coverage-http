# =========================================================
# 🧱 Base builder stage — installs dependencies
# =========================================================
FROM python:3.11-slim AS base

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .

# =========================================================
# 🚀 Production image
# =========================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Copy installed packages and app from base
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /app /app

# Non-root user for security
USER 65532:65532

# Run with Gunicorn (production-ready WSGI server)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "app:app"]

# =========================================================
# 🧪 Test image with coverage wrapper (Kubernetes-ready)
# =========================================================
FROM base AS test

# Install Gunicorn for production-like testing
RUN pip install --no-cache-dir gunicorn

# --- Coverage instrumentation setup ---

# 1. Install sitecustomize.py to auto-start coverage in ALL processes
#    This is the key to capturing coverage in forked Gunicorn workers
COPY server/sitecustomize.py /tmp/sitecustomize.py
RUN SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])") && \
    cp /tmp/sitecustomize.py "$SITE_PACKAGES/sitecustomize.py"

# 2. Copy coverage configuration (.coveragerc)
#    Configures parallel mode and /dev/shm for data storage
COPY server/.coveragerc /app/.coveragerc

# 3. Copy Gunicorn hooks for coverage (worker_exit saves coverage data)
COPY server/gunicorn_coverage.py /opt/gunicorn_coverage.py

# 4. Copy the coverage HTTP server/wrapper
COPY server/coverage_server.py /opt/coverage_server.py

# --- Environment configuration ---

# Tell coverage.py where to find its config (enables multiprocessing support)
ENV COVERAGE_PROCESS_START=/app/.coveragerc

# Coverage HTTP endpoint port
ENV COVERAGE_PORT=9095

# Coverage data directory (must be writable - /dev/shm always is in K8s!)
ENV COVERAGE_DATA_DIR=/dev/shm

# Use /dev/shm for ALL temp files (Gunicorn worker files, etc.)
# This avoids needing a writable /tmp with readOnlyRootFilesystem
ENV TMPDIR=/dev/shm

# Expose coverage endpoint
EXPOSE 9095

# Non-root user for security
USER 65532:65532

# --- Run command ---
# Uses coverage_server.py as a wrapper that:
# 1. Sets up coverage environment
# 2. Runs Gunicorn with coverage hooks
# 3. Provides HTTP endpoint for coverage retrieval

CMD ["python", "/opt/coverage_server.py", "-m", "gunicorn", \
     "-c", "/opt/gunicorn_coverage.py", \
     "-b", "0.0.0.0:8080", \
     "-w", "1", \
     "app:app"]
