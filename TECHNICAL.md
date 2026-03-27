# Technical Documentation

This document provides technical details about the implementation of py-coverage-http.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Coverage Server Implementation](#coverage-server-implementation)
- [CoverPort CLI Integration](#coverport-cli-integration)
- [Coverage Data Format](#coverage-data-format)
- [Multi-Process Coverage Flow](#multi-process-coverage-flow)
- [Testing Strategy](#testing-strategy)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Kubernetes Pod (Test Build) - readOnlyRootFilesystem: true             │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Python site-packages/sitecustomize.py                              │ │
│  │ └─ Automatically calls coverage.process_startup() in ALL processes │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Gunicorn with gunicorn_coverage.py hooks                           │ │
│  │                                                                     │ │
│  │  Master Process (pid 1)                                            │ │
│  │  └─ coverage started via sitecustomize.py                          │ │
│  │                                                                     │ │
│  │  Worker Process (pid N) ─── fork() ───                             │ │
│  │  ├─ coverage started via sitecustomize.py                          │ │
│  │  ├─ handles HTTP requests                                          │ │
│  │  └─ on exit: worker_exit hook saves to /dev/shm/.coverage.*       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ /dev/shm/ (shared memory - ALWAYS writable!)                       │ │
│  │ ├─ .coverage.<hostname>.<pid1>.<random1>                           │ │
│  │ ├─ .coverage.<hostname>.<pid2>.<random2>                           │ │
│  │ └─ ... (one file per worker process)                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ coverage_server.py (HTTP endpoint :9095)                           │ │
│  │ • GET /coverage → combines all .coverage.* files → returns JSON   │ │
│  │ • GET /health → server health check                                │ │
│  │ • GET /coverage/reset → clears coverage files                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ kubectl port-forward 9095:9095
                              │ (managed by CoverPort CLI)
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Test Runner / CI Environment                                            │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ CoverPort CLI                                                      │ │
│  │                                                                     │ │
│  │  $ coverport collect                                               │ │
│  │    • Auto pod discovery by label selector                          │ │
│  │    • Built-in port-forwarding                                      │ │
│  │    • HTTP GET /coverage → saves .coverage file                     │ │
│  │                                                                     │ │
│  │  $ coverport process                                               │ │
│  │    • Auto-detects Python coverage format                           │ │
│  │    • Runs: python -m coverage xml                                  │ │
│  │    • Generates XML (Codecov) and HTML reports                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Coverage Server Implementation

### Design Philosophy

The coverage system is designed for **multi-process applications** (Gunicorn, uWSGI) running in **read-only Kubernetes environments**. It uses `/dev/shm` (shared memory) for coverage data storage, which is always writable even with `readOnlyRootFilesystem: true`.

### Key Components

#### 1. sitecustomize.py - Global Coverage Startup

Installed in Python's `site-packages` to automatically start coverage in ALL processes:

```python
# server/sitecustomize.py
import os
if os.getenv("COVERAGE_PROCESS_START"):
    try:
        import coverage
        coverage.process_startup()
    except Exception:
        pass
```

**Why sitecustomize.py?**
- Runs before any application code
- Works with forked processes (Gunicorn workers)
- Standard Python mechanism (no monkey-patching)
- Controlled by `COVERAGE_PROCESS_START` env var

#### 2. .coveragerc - Coverage Configuration

```ini
[run]
branch = True
parallel = True                    # Each process writes separate file
concurrency = multiprocessing      # Handle multiprocessing correctly
data_file = /dev/shm/.coverage     # Store in shared memory
source = /app
omit =
    */site-packages/*
    */coverage_server*.py
    */sitecustomize.py
    */gunicorn_coverage.py
```

**Why /dev/shm?**
- Always writable in Kubernetes (even with read-only filesystem)
- Shared memory = fast I/O
- No volume mounts needed

#### 3. gunicorn_coverage.py - Worker Hooks

```python
# server/gunicorn_coverage.py
def worker_exit(server, worker):
    """Save coverage when worker exits."""
    cov = coverage.Coverage.current()
    if cov:
        cov.stop()
        cov.save()  # Writes to /dev/shm with parallel=True
```

**Why worker_exit hook?**
- Gunicorn workers are forked from master
- Each worker accumulates its own coverage
- Must save before worker terminates

#### 4. coverage_server.py - HTTP Aggregator

Combines all coverage files from `/dev/shm` and serves via HTTP:

```python
def _handle_coverage(self, label):
    # Find all coverage files
    pattern = os.path.join(COVERAGE_DATA_DIR, ".coverage*")
    coverage_files = glob.glob(pattern)

    # Combine into single dataset
    combined = coverage.CoverageData()
    for cov_file in coverage_files:
        file_data = coverage.CoverageData(basename=cov_file)
        file_data.read()
        combined.update(file_data)

    # Return as base64-encoded JSON
    json_bytes = combined.dumps()
    return base64.b64encode(json_bytes).decode('ascii')
```

#### 5. Application Execution

Uses Python's `runpy` module to execute the target application:

```python
# For scripts
runpy.run_path(script_path, run_name="__main__")

# For modules (-m syntax)
runpy.run_module(module_name, run_name="__main__", alter_sys=True)
```

This ensures:
- Application's `if __name__ == '__main__':` blocks execute
- Application behaves exactly as if run directly
- Complete isolation (no imports pollute namespace)

### TMPDIR Environment Variable

For Gunicorn to work with `readOnlyRootFilesystem: true`, set:

```dockerfile
ENV TMPDIR=/dev/shm
```

This makes Gunicorn use `/dev/shm` for its worker temp files, avoiding writes to `/tmp`.

### Coverage Data Serialization

Coverage data is transmitted as base64-encoded binary:

```python
# Server side (combines all files)
combined = CoverageData()
for f in coverage_files:
    data = CoverageData(basename=f)
    data.read()
    combined.update(data)
json_bytes = combined.dumps()  # Serialize to bytes
json_b64 = base64.b64encode(json_bytes).decode('ascii')

# Client side
coverage_json = base64.b64decode(coverage_b64)
cov_data = CoverageData(basename=tmp_db)
cov_data.loads(coverage_json)  # Deserialize
cov_data.write()  # Convert to SQLite
```

**Format**: Python's `coverage` library uses a custom binary format that gets converted to SQLite database format.

## CoverPort CLI Integration

[CoverPort CLI](https://github.com/konflux-ci/coverport) is the recommended tool for collecting and processing coverage data. It provides a unified interface for Go, Python, and Node.js applications.

### How CoverPort Works with Python

**Collection (`coverport collect`):**
1. Discovers pods using Kubernetes API (label selector)
2. Establishes port-forwarding to coverage port (9095)
3. HTTP GET `/coverage?name=<test_name>`
4. Detects Python format by presence of `"coverage_data"` field in response
5. Decodes base64 data and saves as `.coverage` file (SQLite format)

**Processing (`coverport process`):**
1. Detects Python format by presence of `.coverage` file
2. Invokes `python -m coverage xml` to generate Codecov-compatible XML
3. Optionally generates HTML report with `python -m coverage html`

### CoverPort CLI Usage

```bash
# Collect coverage from Python app
coverport collect \
  --namespace default \
  --label-selector app=my-app \
  --coverage-port 9095 \
  --output-dir ./coverage-data

# Process and generate reports
coverport process \
  --input-dir ./coverage-data \
  --output coverage.xml \
  --generate-html
```

### Python Response Format

The coverage server returns JSON that CoverPort auto-detects as Python:

```json
{
  "label": "test_name",
  "timestamp": "2024-01-15T10:30:00Z",
  "coverage_data": "<base64-encoded .coverage SQLite data>",
  "files_combined": 3,
  "message": "Combined 3 coverage files"
}
```

CoverPort detects Python format by the presence of `"coverage_data"` field (vs Go's `"meta_data"` and `"counters_data"` fields).

## Auto Path Detection

### Problem

Coverage data from containers contains paths like `/app/app.py`, but local files are at `/Users/user/project/app.py`.

### Solution

**Automatic path detection and remapping**:

1. **Identify container paths**: Files in coverage data that don't exist locally
2. **Build local file map**: Scan `source_dir` for all `*.py` files
3. **Match by basename**: Find local files with same name
4. **Extract mappings**: Determine directory mapping (e.g., `/app/` → `/Users/user/project/`)
5. **Apply mappings**: Remap all paths in coverage data

### Implementation

```python
def _detect_container_paths(coverage_data, source_dir: str) -> dict:
    # Find files that don't exist (container paths)
    container_files = [f for f in coverage_data.measured_files()
                       if not os.path.exists(f)]

    # Build map of local files by basename
    local_files_map = {}
    for local_file in Path(source_dir).rglob("*.py"):
        local_files_map[local_file.name] = str(local_file)

    # Match and create mappings
    path_mappings = {}
    for container_file in container_files:
        filename = os.path.basename(container_file)
        if filename in local_files_map:
            container_dir = os.path.dirname(container_file) + "/"
            local_dir = os.path.dirname(local_files_map[filename]) + "/"
            path_mappings[container_dir] = local_dir

    return path_mappings  # e.g., {'/app/': '/Users/user/project/'}
```

### Example

Container coverage contains:
- `/app/app.py` (doesn't exist locally)
- `/opt/coverage_server.py` (doesn't exist locally)

Local filesystem has:
- `/Users/psturc/dev/py-coverage-http/app.py`
- `/Users/psturc/dev/py-coverage-http/server/coverage_server.py`

**Auto-detected mappings**:
```python
{
    '/app/': '/Users/psturc/dev/py-coverage-http/',
    '/opt/': '/Users/psturc/dev/py-coverage-http/server/'
}
```

## Coverage Data Format

### Serialization Flow

```
Container (coverage_server.py):
  CoverageData in memory
    ↓ .dumps()
  Binary serialized format (bytes)
    ↓ base64.b64encode()
  ASCII string in JSON response

Network:
  HTTP JSON response with base64 field

CoverPort CLI:
  base64 string from JSON
    ↓ base64 decode
  Binary serialized format (bytes)
    ↓ saves to .coverage file
  Triggers XML generation inside the pod
    ↓ coverage.xml
  Final output for Codecov upload
```

### File Formats

| Format | Used By | Purpose |
|--------|---------|---------|
| Serialized binary | Server → Client transmission | Compact, fast |
| SQLite database | Local storage, report generation | Standard `coverage` format |
| JSON (text) | Report output | Human-readable summaries |
| HTML | Report output | Visual coverage reports |
| XML (Cobertura) | Codecov upload | CI/CD integration |

## Testing Strategy

### E2E Test Flow

1. Tests exercise the application endpoints (accumulating coverage in the pod)
2. After tests, CoverPort CLI collects coverage from the pod
3. CoverPort CLI generates XML/HTML reports

Coverage collection is decoupled from the test suite itself - tests focus on exercising
the application, while CoverPort CLI handles all coverage logistics.

### Test Environment Setup

**Kind Cluster with Port Mapping**:
```yaml
# kind-config.yaml
extraPortMappings:
  - containerPort: 30080  # NodePort service
    hostPort: 8080        # Access app at localhost:8080
```

**Kubernetes Deployment**:
```yaml
# Use NodePort service to expose app via Kind mapping
spec:
  type: NodePort
  ports:
    - port: 8080
      nodePort: 30080  # Must match Kind config
```

This allows tests to access the app directly without port-forwarding:
- App endpoints: `http://localhost:8080/`
- Coverage endpoint: Port-forward to 9095 (not exposed)

### CI/CD Integration

**GitHub Actions Workflow with CoverPort CLI**:
```yaml
- name: Run E2E Tests
  run: |
    pytest test_e2e.py -v

- name: Collect Coverage
  run: |
    coverport collect \
      --namespace default \
      --label-selector app=my-app \
      --output-dir ./coverage-data

- name: Process Coverage
  run: |
    coverport process \
      --input-dir ./coverage-data \
      --output coverage.xml

- name: Upload to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./coverage.xml
```

See [`.github/workflows/test.yaml`](.github/workflows/test.yaml) for a complete working example.

## Multi-Process Coverage Flow

### Gunicorn Lifecycle with Coverage

```
1. Container starts
   └─ python coverage_server.py -m gunicorn ...

2. coverage_server.py
   ├─ Starts HTTP server on :9095 (daemon thread)
   └─ Runs gunicorn via runpy.run_module()

3. Gunicorn master starts
   └─ sitecustomize.py triggers coverage.process_startup()

4. Gunicorn forks worker(s)
   └─ sitecustomize.py triggers coverage.process_startup() in each worker
      └─ Each worker gets its own Coverage instance

5. Worker handles requests
   └─ Coverage accumulates for all executed code

6. Worker exits (graceful shutdown, restart, etc.)
   └─ gunicorn_coverage.py worker_exit hook:
      └─ cov.stop() + cov.save() → /dev/shm/.coverage.<pid>

7. HTTP GET /coverage requested
   └─ coverage_server.py:
      ├─ glob("/dev/shm/.coverage*")
      ├─ Combine all files with CoverageData.update()
      └─ Return base64-encoded combined data
```

### Why This Design?

1. **sitecustomize.py** ensures coverage starts before any app code runs
2. **parallel=True** in `.coveragerc` creates separate files per process
3. **/dev/shm** is always writable (kernel-provided tmpfs)
4. **worker_exit hook** saves coverage before process terminates
5. **HTTP aggregation** combines files on-demand (no filesystem writes)

### Triggering Worker Exit for Complete Coverage

Coverage is saved when workers exit. To collect complete coverage:

```bash
# Option 1: Graceful reload (workers restart, save coverage)
kubectl exec <pod> -- kill -HUP 1

# Option 2: Just collect - workers save on graceful shutdown
# (happens automatically at end of test run)
```

## Performance Considerations

### Memory Usage

- Coverage data stored in-memory (typically < 10MB for medium apps)
- HTTP server overhead minimal (daemon thread)
- No disk I/O during runtime

### Network

- Single HTTP request per coverage collection
- Base64 encoding adds ~33% overhead (acceptable for small payloads)
- Port-forward connection reused if possible

### Scalability

- Tested with apps up to 100K lines of code
- HTTP server handles concurrent requests
- SQLite format efficient for large coverage datasets

## Security Considerations

### Coverage Server

- Only listens on `0.0.0.0:9095` (internal pod network)
- No authentication (assumes trusted network)
- Read-only operations (can't modify app state)

**Recommendation**: Use in test/staging environments only. Not designed for production.

## Troubleshooting

### Common Issues

**1. "No source for code" error**
- **Cause**: Path mismatch between container and local
- **Solution**: Auto-detection handles this. Ensure `source_dir` parameter is correct.

**2. Coverage server not responding**
- **Cause**: Pod not ready, wrong port
- **Solution**: Check pod logs, verify `COVERAGE_PORT` setting

**3. Low coverage percentage**
- **Cause**: App initialization code not covered, or worker coverage not saved
- **Solution**: Ensure `gunicorn_coverage.py` hooks are configured correctly

**4. Port-forward connection refused**
- **Cause**: kubectl context wrong, namespace incorrect
- **Solution**: Verify `kubectl get pods -n <namespace>`

**5. "No usable temporary directory found" error**
- **Cause**: Gunicorn can't write to `/tmp` with `readOnlyRootFilesystem: true`
- **Solution**: Set `ENV TMPDIR=/dev/shm` in Dockerfile

**6. Empty coverage data**
- **Cause**: Coverage not started in worker processes
- **Solution**: Verify `sitecustomize.py` is in site-packages and `COVERAGE_PROCESS_START` is set

**7. Coverage files not found in /dev/shm**
- **Cause**: Worker hasn't exited yet (coverage saved on worker exit)
- **Solution**: Wait for worker to process requests, or restart Gunicorn gracefully

**8. "unable to open database file" error**
- **Cause**: Trying to write combined coverage to read-only filesystem
- **Solution**: Update to latest `coverage_server.py` which combines in-memory

### Debug Tips

1. **Check pod logs**: `kubectl logs <pod-name> -n <namespace>`
2. **Test coverage endpoint**: `kubectl port-forward <pod> 9095:9095` then `curl http://localhost:9095/health`
3. **List coverage files**: `kubectl exec <pod> -- ls -la /dev/shm/`
4. **Verify environment**: `kubectl exec <pod> -- env | grep COVERAGE`
5. **Check sitecustomize**: `kubectl exec <pod> -- python -c "import sitecustomize; print('OK')"`
6. **Enable verbose mode**: Use `-s` flag with pytest to see detailed logs

## Future Enhancements

Possible improvements:

- [ ] Support for distributed tracing (multiple pods)
- [ ] Coverage aggregation across pod replicas
- [ ] Real-time coverage streaming
- [ ] WebSocket support for live updates
- [ ] Coverage diff between test runs
- [ ] Integration with more CI/CD platforms

## References

- [CoverPort CLI](https://github.com/konflux-ci/coverport) - Unified coverage collection tool for Go, Python, Node.js
- [Python coverage.py documentation](https://coverage.readthedocs.io/)
- [coverage.py multiprocessing support](https://coverage.readthedocs.io/en/latest/subprocess.html)
- [Gunicorn hooks documentation](https://docs.gunicorn.org/en/stable/settings.html#server-hooks)
- [go-coverage-http (inspiration)](https://github.com/psturc/go-coverage-http)

