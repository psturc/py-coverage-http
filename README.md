# py-coverage-http

Collect Python code coverage from running applications via HTTP - no volumes, no writable filesystems, no deployment modifications needed.

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
* 📊 **Report Generation** - Generate text and HTML coverage reports
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

# Option A: Discover pod automatically by label
pod_name = CoverageClient.get_pod_name("default", label_selector="app=my-app")

# Option B: Use a known pod name
pod_name = "my-pod-574fb6f489-abc12"

# Collect from Kubernetes pod (uses kubectl binary by default)
client.collect_coverage_from_pod(
    pod_name=pod_name,
    test_name="my-test",
    coverage_port=9095
)

# Or use native Python port-forward (no kubectl binary required!)
client.collect_coverage_from_pod(
    pod_name=pod_name,
    test_name="my-test",
    coverage_port=9095,
    use_kubectl=False  # Use native Python
)

# Generate reports with automatic path remapping
client.generate_coverage_report("my-test")
client.generate_html_report("my-test")
```

### 3. Upload Coverage to Codecov (Optional)

Coverage data can be easily uploaded to Codecov via GitHub Actions. See the workflow example in this repository.

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

The `CoverageClient` supports two methods for port-forwarding:

### kubectl Binary Method (Default, Recommended)

```python
client.collect_coverage_from_pod(
    pod_name="my-pod",
    test_name="test"
    # use_kubectl=True  # Default
)
```

**Requires**: `kubectl` binary in PATH

**Pros**:
- ✅ Battle-tested and reliable
- ✅ Works everywhere kubectl works
- ✅ No additional Python packages needed
- ✅ Proven in production

**Cons**:
- ⚠️ Requires kubectl binary installed

### Native Python Port-Forward (Works!)

```python
client.collect_coverage_from_pod(
    pod_name="my-pod",
    test_name="test",
    use_kubectl=False  # Use native Python
)
```

**Requires**: `pip install kubernetes`

**Pros**:
- ✅ No external binary dependencies (no kubectl required!)
- ✅ Pure Python solution
- ✅ Now fully functional

**Cons**:
- ⚠️ Requires kubernetes Python package
- ⚠️ Slightly less battle-tested than kubectl

**Recommendation**: kubectl (default) is more proven, but native Python works great if you prefer no binary dependencies.

## How It Works

### Coverage Server

The `coverage_server.py` wrapper:

1. Starts Python `coverage` in-memory mode (no file writes)
2. Imports and runs your application in a background thread
3. Starts an HTTP server on `COVERAGE_PORT`
4. Provides endpoints to dump coverage data as base64-encoded JSON

### Client Library

The `CoverageClient`:

1. Uses `kubectl port-forward` to connect to the pod
2. Fetches coverage data from `/coverage` endpoint
3. Decodes and saves coverage files locally
4. Generates text and HTML reports using Python's `coverage` library

## Architecture

```
┌─────────────────────────────────────────┐
│  Kubernetes Pod                         │
│  ┌───────────────────────────────────┐  │
│  │ coverage_server.py (wrapper)      │  │
│  │                                   │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │ Your Application (app.py)   │  │  │
│  │  │ Running on port 8080        │  │  │
│  │  └─────────────────────────────┘  │  │
│  │                                   │  │
│  │  Coverage HTTP Server (9095)     │  │
│  │  - /coverage                     │  │
│  │  - /health                       │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                  │
                  │ kubectl port-forward
                  │
┌─────────────────▼─────────────────────┐
│  Test Runner                          │
│  ┌─────────────────────────────────┐  │
│  │ CoverageClient                  │  │
│  │ - Port-forward to pod           │  │
│  │ - Fetch coverage via HTTP       │  │
│  │ - Generate reports              │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

