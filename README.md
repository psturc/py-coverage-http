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

* ✅ No writable filesystem needed (coverage stored in-memory)
* ✅ No volume mounts required
* ✅ No deployment manifest changes
* ✅ Just download `coverage_server.py` during build
* ✅ Collect coverage via HTTP with provided client library
* ✅ Works with any Python framework (Flask, Django, FastAPI, etc.)

## How it works

1. **Build time**: Download `coverage_server.py` and include it in your test Docker image
2. **Runtime**: Coverage server automatically starts on port 9095, wraps your application
3. **Test time**: Client library collects coverage via HTTP port-forwarding
4. **Result**: Coverage reports generated automatically

## Features

* 🎯 **Pure Wrapper** - Completely application-agnostic! Works like `coverage run script.py`
* 🚀 **HTTP Coverage Server** - Automatically exposes coverage via HTTP
* 🔌 **Client Library** - Collects coverage via kubectl port-forward or native Python
* 🔍 **Pod Discovery** - Automatically find pods by label selector (no hardcoded names!)
* 🗺️ **Auto Path Remapping** - Automatically maps container paths to local paths
* 📊 **Report Generation** - Generate text, HTML, and XML (Codecov) reports
* 🎭 **Smart Filtering** - Excludes instrumentation code from coverage
* 🐳 **Kubernetes-friendly** - No volumes, no writable filesystem needed
* 💾 **In-Memory Storage** - Coverage data stored in memory, retrieved via HTTP
* 🌐 **Framework Agnostic** - Flask, Django, FastAPI, or plain Python scripts

## Quick Start

### 1. Add Coverage Server to Your App

The `coverage_server.py` is a **pure wrapper** - completely application-agnostic!  
Just run your script through it like `coverage run`:

```dockerfile
# Test image with coverage wrapper
FROM base AS test

# Install coverage dependency only in test build
RUN pip install coverage

# Download the pure coverage wrapper
RUN wget https://raw.githubusercontent.com/psturc/py-coverage-http/main/server/coverage_server.py \
    -O /opt/coverage_server.py

# Environment variables
ENV COVERAGE_PORT=9095

# Run your app through the wrapper - completely application-agnostic!
CMD ["python", "/opt/coverage_server.py", "/app/app.py"]
```

The coverage wrapper will:
- Start coverage collection
- Execute your script (any Python file, any framework!)
- Start HTTP server on port 9095 (configurable via `COVERAGE_PORT`)
- Provide coverage data via HTTP endpoints

**Works with ANY Python application** - Flask, Django, FastAPI, or plain scripts!

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
* `coverage_server.py` - Coverage wrapper (downloads from GitHub in production)
* `Dockerfile` - Multi-stage build with test target
* `k8s-deployment.yaml` - Kubernetes deployment manifest
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

## Usage

The coverage wrapper is a pure command-line tool:

```bash
# Basic usage
python coverage_server.py app.py

# With module syntax
python coverage_server.py -m flask run

# Any Python script!
python coverage_server.py path/to/your/script.py

# Pass arguments to your script
python coverage_server.py app.py --host 0.0.0.0 --port 8080
```

All arguments after the script name are passed to your application.

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

**Simple 3-step process:**

1. **Coverage Server** wraps your app, starts HTTP server on port 9095
2. **Port-Forward** connects test runner to pod (kubectl or native Python)
3. **Client Library** fetches coverage, generates reports with auto path remapping

```
┌─────────────────────────┐
│  Kubernetes Pod         │
│  coverage_server.py     │
│  ├─ Your App (8080)     │
│  └─ HTTP Server (9095)  │
└──────────┬──────────────┘
           │ Port-forward
┌──────────▼──────────────┐
│  Test Runner            │
│  CoverageClient         │
│  ├─ Fetch via HTTP      │
│  ├─ Remap paths         │
│  └─ Generate reports    │
└─────────────────────────┘
```

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

