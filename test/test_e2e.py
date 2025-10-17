"""
E2E tests that collect coverage from running pods.

This test suite leverages Kind's extraPortMappings to access the application
directly at localhost:8080 (no kubectl port-forward needed for app endpoints).

For coverage collection (port 9095), it uses the CoverageClient which supports both:
- kubectl port-forward (default, reliable)
- Native Python port-forward (no kubectl binary required)

Environment Variables:
- USE_KUBECTL=true|false          - Port-forward method (default: false)
- GENERATE_HTML_REPORTS=true|false - Generate HTML reports (default: false, for CI)
- K8S_NAMESPACE=<namespace>        - Kubernetes namespace (default: coverage-demo)

Coverage collection flow:
1. Tests run
2. AFTER ALL TESTS: Collect coverage from the pod
3. Generate reports:
   - XML report (always, for CI/Codecov, with path remapping)
   - Text report (always, with path remapping)
   - HTML report (if GENERATE_HTML_REPORTS=true, with path remapping)
"""

import os
import sys
import time
import requests
import pytest

# Add parent directory to path to import client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from client.coverage_client import CoverageClient


# Configuration
NAMESPACE = os.getenv("K8S_NAMESPACE", "coverage-demo")
APP_URL = "http://localhost:8080"  # App exposed via Kind's extraPortMappings
COVERAGE_PORT = 9095

# Port-forward method for coverage collection (port 9095 only)
# True = kubectl binary (default, reliable)
# False = Native Python
USE_KUBECTL_FOR_COVERAGE = os.getenv("USE_KUBECTL", "false").lower() == "true"

# HTML report generation (disabled by default for CI)
# True = Generate HTML reports
# False = Skip HTML generation (only collect coverage data)
GENERATE_HTML_REPORTS = os.getenv("GENERATE_HTML_REPORTS", "false").lower() == "true"


@pytest.fixture(scope="session")
def pod_name():
    """
    Dynamically discover the pod name based on label selector.
    Uses CoverageClient.get_pod_name() for pod discovery.
    """
    name = CoverageClient.get_pod_name(NAMESPACE, label_selector="app=coverage-demo")
    print(f"\n[test] Discovered pod: {name}")
    return name


@pytest.fixture(scope="session")
def coverage_client():
    """
    Create a coverage client for the test session.
    
    Uses native Python port-forwarding by default (no kubectl binary required).
    Set USE_KUBECTL=true environment variable to use kubectl binary.
    """
    client = CoverageClient(namespace=NAMESPACE, output_dir="./coverage-output")
    
    # Log which method will be used
    method = "kubectl binary" if USE_KUBECTL_FOR_COVERAGE else "native Python"
    print(f"\n[test] Coverage client configured with {method} port-forwarding")
    
    return client


@pytest.fixture(scope="session", autouse=True)
def collect_coverage_after_tests(coverage_client, pod_name):
    """
    Collect coverage from the pod after all tests complete.
    
    This simple fixture:
    1. Lets all tests run (accumulating coverage)
    2. Collects coverage once at the end
    3. Generates reports (text always, HTML if GENERATE_HTML_REPORTS=true)
    """
    # Let tests run
    yield
    
    # After all tests complete - collect coverage
    print("\n" + "="*60)
    print("All tests complete - collecting coverage...")
    print("="*60)
    
    try:
        # Collect coverage from the pod
        coverage_file = coverage_client.collect_coverage_from_pod(
            pod_name=pod_name,
            test_name="e2e_tests",
            coverage_port=COVERAGE_PORT,
            use_kubectl=USE_KUBECTL_FOR_COVERAGE
        )
        
        if coverage_file:
            print(f"[coverage] ✓ Coverage collected: {coverage_file}")
            
            # Generate text report (always, with path remapping)
            print("[coverage] Generating text coverage report...")
            try:
                coverage_client.generate_coverage_report("e2e_tests", source_dir="..", remap_paths=True)
            except Exception as e:
                print(f"[coverage] ⚠ Text report generation failed: {e}")
            
            # Generate XML report (always, for CI/Codecov, with path remapping)
            print("[coverage] Generating XML coverage report...")
            try:
                coverage_client.generate_xml_report("e2e_tests", source_dir="..", remap_paths=True)
            except Exception as e:
                print(f"[coverage] ⚠ XML generation failed: {e}")
            
            # Generate HTML report (if enabled, with path remapping)
            if GENERATE_HTML_REPORTS:
                print("[coverage] Generating HTML coverage report...")
                coverage_client.generate_html_report("e2e_tests", source_dir="..", remap_paths=True)
                print("\n" + "="*60)
                print("Coverage Reports Generated:")
                print("="*60)
                print("📊 HTML Report:  ./coverage-output/html_e2e_tests/index.html")
                print("📄 Text Report:  ./coverage-output/report_e2e_tests.txt")
                print("📦 XML Report:   ./coverage-output/coverage.xml")
                print("💾 Coverage Data: ./coverage-output/.coverage_e2e_tests")
                print("="*60)
            else:
                print("\n" + "="*60)
                print("Coverage Data Collected:")
                print("="*60)
                print("📄 Text Report:  ./coverage-output/report_e2e_tests.txt")
                print("📦 XML Report:   ./coverage-output/coverage.xml")
                print("💾 Coverage Data: ./coverage-output/.coverage_e2e_tests")
                print("="*60)
        else:
            print("[coverage] ⚠ Failed to collect coverage")
            
    except Exception as e:
        print(f"[coverage] ⚠ Error collecting coverage: {e}")
        import traceback
        traceback.print_exc()


def test_index_endpoint(coverage_client):
    """Test the index endpoint."""
    response = requests.get(f"{APP_URL}/")
    assert response.status_code == 200
    assert "Hello" in response.text
    print(f"[test] ✓ Index endpoint returned: {response.text}")


def test_status_endpoint(coverage_client):
    """Test the status endpoint."""
    response = requests.get(f"{APP_URL}/status")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    print(f"[test] ✓ Status endpoint returned: {data}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

