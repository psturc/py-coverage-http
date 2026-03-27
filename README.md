# py-coverage-http

Collect Python code coverage from running applications via HTTP - no volumes, no writable filesystems, no deployment modifications needed.

Inspired by [go-coverage-http](https://github.com/psturc/go-coverage-http) - now available for Python!

## Why?

Traditional coverage collection requires:

* ❌ Writable filesystem for coverage data files
* ❌ Mounting volumes in Kubernetes for coverage data
* ❌ Modifying deployment manifests to add volume mounts
* ❌ Extracting files from volumes after tests

**This solution eliminates all of that:**

* ✅ Works with `readOnlyRootFilesystem: true` (uses `/dev/shm`)
* ✅ No volume mounts required
* ✅ No deployment manifest changes
* ✅ Just download instrumentation files during build
* ✅ Collect coverage via HTTP using [CoverPort CLI](https://github.com/konflux-ci/coverport)
* ✅ Works with any Python framework (Flask, Django, FastAPI, etc.)
* ✅ **Supports Gunicorn and multi-process applications**

## How it works

1. **Build time**: Download instrumentation files and include in your test Docker image
2. **Runtime**: Coverage collection starts automatically in all processes (including Gunicorn workers)
3. **Test time**: Collect coverage via HTTP using [CoverPort CLI](https://github.com/konflux-ci/coverport)
4. **Result**: Coverage reports generated automatically (XML for Codecov, HTML for viewing)

## Features

* 🎯 **Multi-Process Support** - Works with Gunicorn, uWSGI, and other WSGI servers
* 🚀 **HTTP Coverage Server** - Automatically exposes combined coverage via HTTP
* 🔌 **CoverPort CLI Integration** - Collect and process coverage with unified CLI tool
* 🔍 **Pod Discovery** - Automatically find pods by label selector (no hardcoded names!)
* 🗺️ **Auto Path Remapping** - Automatically maps container paths to local paths
* 📊 **Report Generation** - Generate text, HTML, and XML (Codecov) reports
* 🎭 **Smart Filtering** - Excludes instrumentation code from coverage
* 🐳 **Kubernetes-friendly** - Works with `readOnlyRootFilesystem: true`
* 💾 **/dev/shm Storage** - Coverage data stored in shared memory (always writable)
* 🌐 **Framework Agnostic** - Flask, Django, FastAPI, or plain Python scripts

## Quick Start

### 1. Add Coverage Instrumentation to Your App

Download the required instrumentation files:

```bash
# Coverage HTTP server/wrapper
curl -o server/coverage_server.py \
  https://raw.githubusercontent.com/psturc/py-coverage-http/main/server/coverage_server.py

# Auto-starts coverage in all Python processes (required for Gunicorn)
curl -o server/sitecustomize.py \
  https://raw.githubusercontent.com/psturc/py-coverage-http/main/server/sitecustomize.py

# Gunicorn hooks to save coverage on worker exit
curl -o server/gunicorn_coverage.py \
  https://raw.githubusercontent.com/psturc/py-coverage-http/main/server/gunicorn_coverage.py

# Coverage configuration for parallel/multiprocess mode
curl -o server/.coveragerc \
  https://raw.githubusercontent.com/psturc/py-coverage-http/main/server/.coveragerc
```

Add a test stage to your Dockerfile:

```dockerfile
# Test image with coverage instrumentation
FROM base AS test

# Install coverage and gunicorn
RUN pip install coverage>=7.0.0 gunicorn>=21.0.0

# Install sitecustomize.py to auto-start coverage in ALL processes
COPY server/sitecustomize.py /tmp/sitecustomize.py
RUN SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])") && \
    cp /tmp/sitecustomize.py "$SITE_PACKAGES/sitecustomize.py"

# Copy coverage configuration and hooks
COPY server/.coveragerc /app/.coveragerc
COPY server/gunicorn_coverage.py /opt/gunicorn_coverage.py
COPY server/coverage_server.py /opt/coverage_server.py

# Environment configuration
ENV COVERAGE_PROCESS_START=/app/.coveragerc
ENV COVERAGE_PORT=9095
ENV COVERAGE_DATA_DIR=/dev/shm
ENV TMPDIR=/dev/shm  # Critical for readOnlyRootFilesystem!

EXPOSE 9095

# Run Gunicorn through coverage wrapper
CMD ["python", "/opt/coverage_server.py", "-m", "gunicorn", \
     "-c", "/opt/gunicorn_coverage.py", \
     "-b", "0.0.0.0:8080", \
     "-w", "1", \
     "app:app"]
```

**Key points:**
- `sitecustomize.py` ensures coverage starts in all processes (master + workers)
- `gunicorn_coverage.py` saves coverage data when workers exit
- `/dev/shm` is always writable, even with `readOnlyRootFilesystem: true`
- `TMPDIR=/dev/shm` makes Gunicorn use shared memory for temp files

### 2. Collect Coverage from Tests

Use [CoverPort CLI](https://github.com/konflux-ci/coverport) to collect coverage. It supports Go, Python, and Node.js applications with a unified interface.

```bash
# Install CoverPort CLI
go install github.com/konflux-ci/coverport/cli@latest

# Discover pods, collect coverage, and generate XML report (all in one step)
coverport collect \
  --namespace default \
  --label-selector app=my-app \
  --coverage-port 9095 \
  --output-dir ./coverage-data
```

For Python, `coverport collect` handles everything: it triggers a coverage save, fetches
the data, and generates Cobertura XML by executing `coverage xml` inside the target pod
(where Python and the `coverage` package are already installed). No separate `process`
step is needed.

**CoverPort CLI features:**
- Auto pod discovery by label selector
- Built-in port-forwarding (no manual setup)
- Auto-detects Python coverage server
- Triggers coverage save and generates XML automatically
- Works with Go, Python, and Node.js

### 3. Upload to Codecov (Optional)

```yaml
# .github/workflows/test.yaml
- name: Collect coverage
  run: |
    coverport collect \
      --namespace default \
      --label-selector app=my-app \
      --output-dir ./coverage-data

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    directory: ./coverage-data
    token: ${{ secrets.CODECOV_TOKEN }}
```

See [`.github/workflows/test.yaml`](.github/workflows/test.yaml) for a complete example.

## Complete Example

This repository includes a working demo application. To try it:

```bash
# Build Docker image with coverage enabled
docker build --target test -t localhost/py-coverage-http:test .

# For Podman users
podman build --target test -t localhost/py-coverage-http:test .

# Deploy to Kubernetes
kubectl apply -f k8s-deployment.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=coverage-demo --timeout=60s

# Run E2E tests against the app
cd test && python -m pytest test_e2e.py -v -s

# Collect coverage with CoverPort CLI (generates XML automatically)
coverport collect \
  --namespace coverage-demo \
  --label-selector app=coverage-demo \
  --output-dir ./coverage-output
```

### Example Files

* `app.py` - Sample Flask application with test endpoints
* `server/coverage_server.py` - Coverage HTTP wrapper
* `server/sitecustomize.py` - Auto-starts coverage in all processes
* `server/gunicorn_coverage.py` - Gunicorn hooks for coverage
* `server/.coveragerc` - Coverage configuration for multiprocessing
* `Dockerfile` - Multi-stage build with test target
* `k8s-example.yaml` - Kubernetes deployment manifest (works with readOnlyRootFilesystem)
* `test/test_e2e.py` - E2E tests that exercise the application endpoints

## API Endpoints

**Application endpoints:**
* `:8080/` - Hello world endpoint
* `:8080/status` - Status check
* `:8080/untested` - Untested endpoint (to demonstrate coverage gaps)

**Coverage endpoints (test builds only):**
* `:9095/coverage?name=<test_name>` - Collect coverage data
* `:9095/health` - Coverage server health check
* `:9095/coverage/reset` - Reset coverage data

## Environment Variables

* `COVERAGE_PORT` - Port for coverage HTTP server (default: `9095`)
* `COVERAGE_DATA_DIR` - Directory for coverage data files (default: `/dev/shm`)
* `COVERAGE_PROCESS_START` - Path to `.coveragerc` (enables multiprocessing)
* `TMPDIR` - Temp directory for Gunicorn (set to `/dev/shm` for read-only filesystems)
* `ENABLE_COVERAGE` - Set to `true` to enable coverage collection

## Usage

The coverage wrapper supports multiple usage patterns:

```bash
# Simple scripts
python coverage_server.py app.py

# With module syntax (recommended for Gunicorn)
python coverage_server.py -m gunicorn -c gunicorn_coverage.py app:app

# Flask development server
python coverage_server.py -m flask run

# Any Python script with arguments
python coverage_server.py app.py --host 0.0.0.0 --port 8080
```

### Gunicorn (Recommended for Production-like Testing)

For Gunicorn applications, use the full instrumentation setup:

```bash
python coverage_server.py -m gunicorn \
    -c /opt/gunicorn_coverage.py \
    -b 0.0.0.0:8080 \
    -w 1 \
    app:app
```

This ensures coverage is collected from all worker processes.

## Coverage Collection

[CoverPort CLI](https://github.com/konflux-ci/coverport) provides a unified interface for collecting coverage from Go, Python, and Node.js applications:

```bash
# Collect coverage and generate XML (all in one step for Python)
coverport collect \
  --namespace default \
  --label-selector app=my-app \
  --coverage-port 9095 \
  --output-dir ./coverage-data
```

For Python, the `collect` command handles the full workflow: it auto-detects the Python
coverage server, triggers a save, fetches coverage data, and generates Cobertura XML by
running `coverage xml` inside the target pod. The output directory will contain
`coverage.xml` ready for upload to Codecov.

**Benefits**:
- Unified tool for Go, Python, Node.js
- Auto-detects Python coverage server
- Built-in port-forwarding (no manual setup)
- No Python needed in the CLI container (uses Python from the target pod)
- Generates Codecov-compatible XML automatically

## How It Works

**Multi-process coverage collection:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Container (read-only FS)                  │
├─────────────────────────────────────────────────────────────┤
│   sitecustomize.py                                          │
│   └─ coverage.process_startup() in EVERY process           │
├─────────────────────────────────────────────────────────────┤
│   Gunicorn                                                  │
│   ├─ Master (pid 1)                                         │
│   └─ Worker (pid N) ─── handles requests                    │
│                                                              │
│   gunicorn_coverage.py hooks:                                │
│   └─ worker_exit: saves coverage to /dev/shm                │
├─────────────────────────────────────────────────────────────┤
│   /dev/shm/ (always writable in K8s!)                        │
│   └─ .coverage.<hostname>.<pid>.<random>                    │
├─────────────────────────────────────────────────────────────┤
│   coverage_server.py (HTTP endpoint :9095)                   │
│   └─ GET /coverage → combines files → returns JSON          │
└─────────────────────────────────────────────────────────────┘
           │ Port-forward (auto-managed)
┌──────────▼──────────────────────────────────────────────────┐
│  Test Runner / CI Environment                                │
│                                                              │
│  CoverPort CLI                                               │
│  └─ coverport collect                                        │
│     ├─ fetches .coverage data via HTTP                      │
│     └─ generates XML via exec into the pod                  │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: `/dev/shm` (shared memory) is always writable in Kubernetes, even with `readOnlyRootFilesystem: true`!

For technical details, see [TECHNICAL.md](TECHNICAL.md).

## Documentation

- **[README.md](README.md)** (this file) - Quick start and usage guide
- **[TECHNICAL.md](TECHNICAL.md)** - Architecture, implementation details, troubleshooting
- **[.github/workflows/test.yaml](.github/workflows/test.yaml)** - CI/CD example with Codecov

## License

MIT License - see LICENSE file for details.

## Credits

Inspired by [go-coverage-http](https://github.com/psturc/go-coverage-http) by the same author.

