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
* ✅ Collect coverage via HTTP with provided client library
* ✅ Works with any Python framework (Flask, Django, FastAPI, etc.)
* ✅ **Supports Gunicorn and multi-process applications**

## How it works

1. **Build time**: Download instrumentation files and include in your test Docker image
2. **Runtime**: Coverage collection starts automatically in all processes (including Gunicorn workers)
3. **Test time**: Client library collects coverage via HTTP port-forwarding
4. **Result**: Coverage reports generated automatically

## Features

* 🎯 **Multi-Process Support** - Works with Gunicorn, uWSGI, and other WSGI servers
* 🚀 **HTTP Coverage Server** - Automatically exposes combined coverage via HTTP
* 🔌 **Client Library** - Collects coverage via kubectl port-forward or native Python
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

```python
from client.coverage_client import CoverageClient

# Create client
client = CoverageClient(namespace="default", output_dir="./coverage-output")

# Discover pod automatically by label (no hardcoded names!)
pod_name = CoverageClient.get_pod_name("default", label_selector="app=my-app")

# Collect coverage from pod
client.collect_coverage_from_pod(
    pod_name=pod_name,
    test_name="my-test",
    coverage_port=9095,
    use_kubectl=False  # Native Python (no kubectl binary needed!)
)

# Generate reports (paths automatically remapped from container to local)
client.generate_coverage_report("my-test")  # Text report
client.generate_html_report("my-test")      # HTML report
client.generate_xml_report("my-test")       # XML for Codecov
```

**Key features:**
- 🔍 Auto pod discovery (no hardcoded names)
- 🗺️ Auto path remapping (container → local paths)
- 🎭 Auto excludes instrumentation code
- 📊 Multiple report formats (text, HTML, XML)

### 3. Upload to Codecov (Optional)

```yaml
# .github/workflows/test.yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./test/coverage-output/coverage.xml
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
kubectl wait --for=condition=ready pod/coverage-demo --timeout=60s

# Run E2E tests (will collect coverage automatically)
cd test && python -m pytest test_e2e.py -v -s
```

The E2E tests will:
* Execute requests against the running pod
* Collect coverage data via port-forwarding
* Generate text and HTML reports in `./coverage-output/`

### Example Files

* `app.py` - Sample Flask application with test endpoints
* `server/coverage_server.py` - Coverage HTTP wrapper
* `server/sitecustomize.py` - Auto-starts coverage in all processes
* `server/gunicorn_coverage.py` - Gunicorn hooks for coverage
* `server/.coveragerc` - Coverage configuration for multiprocessing
* `Dockerfile` - Multi-stage build with test target
* `k8s-example.yaml` - Kubernetes deployment manifest (works with readOnlyRootFilesystem)
* `test/test_e2e.py` - E2E tests with coverage collection
* `client/coverage_client.py` - Client library for collecting coverage

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

## Client Library Options

### Pod Discovery

The `CoverageClient` provides a utility method to discover pods automatically by label:

```python
# Find pod by label selector
pod_name = CoverageClient.get_pod_name(
    namespace="default",
    label_selector="app=my-app"
)

# Use with coverage collection
client.collect_coverage_from_pod(pod_name=pod_name, test_name="test1")
```

**Benefits**:
- ✅ No hardcoded pod names
- ✅ Works across deployments (pod names change with each deployment)
- ✅ Standard Kubernetes label selectors
- ✅ Finds first running pod automatically

### Port-Forwarding Methods

The client supports two methods:

| Method | Pros | Cons |
|--------|------|------|
| **kubectl binary** (default) | Battle-tested, reliable | Requires kubectl binary |
| **Native Python** (`use_kubectl=False`) | No binary deps, pure Python | Requires `kubernetes` package |

Both methods work reliably. Use `use_kubectl=False` for pure Python environments.

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
           │ Port-forward (kubectl or native Python)
┌──────────▼──────────────────────────────────────────────────┐
│  Test Runner / CI Environment                                │
│  CoverageClient                                              │
│  ├─ Fetch combined coverage via HTTP                        │
│  ├─ Auto-remap container paths to local paths               │
│  └─ Generate reports (text, HTML, XML)                      │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: `/dev/shm` (shared memory) is always writable in Kubernetes, even with `readOnlyRootFilesystem: true`!

For technical details, see [TECHNICAL.md](TECHNICAL.md).

## Documentation

- **[README.md](README.md)** (this file) - Quick start and usage guide
- **[TECHNICAL.md](TECHNICAL.md)** - Architecture, implementation details, troubleshooting
- **[.github/workflows/test.yaml](.github/workflows/test.yaml)** - CI/CD example with Codecov
- **[test/test_e2e.py](test/test_e2e.py)** - Complete E2E test example

## License

MIT License - see LICENSE file for details.

## Credits

Inspired by [go-coverage-http](https://github.com/psturc/go-coverage-http) by the same author.

