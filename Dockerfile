# =========================================================
# 🧱 Base builder stage — installs dependencies
# =========================================================
FROM python:3.11-slim AS base

# Set working dir
WORKDIR /app

# Copy the app source and install Python dependencies
COPY . .
RUN pip install -r requirements.txt

# =========================================================
# 🚀 Production image
# =========================================================
FROM python:3.11-slim AS production

WORKDIR /app
COPY --from=base /app /app

# Command for production run
CMD ["python", "-m", "app.py"]

# =========================================================
# 🧪 Test image with coverage wrapper
# =========================================================
FROM base AS test

# Install coverage dependency only in test build
RUN pip install coverage

# Copy the pure wrapper script from server directory
COPY server/coverage_server.py /opt/coverage_server.py

# Environment variables for test
ENV COVERAGE_PORT=9095

# Command for test mode - Run app.py through the coverage wrapper
# The wrapper is completely application-agnostic!
CMD ["python", "/opt/coverage_server.py", "/app/app.py"]