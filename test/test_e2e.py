"""
E2E tests that exercise the application endpoints.

Coverage collection is handled externally by CoverPort CLI
(see .github/workflows/test.yaml).

Environment Variables:
- K8S_NAMESPACE=<namespace>  - Kubernetes namespace (default: coverage-demo)
"""

import os
import requests
import pytest


APP_URL = "http://localhost:8080"


def test_index_endpoint():
    """Test the index endpoint."""
    response = requests.get(f"{APP_URL}/")
    assert response.status_code == 200
    assert "Hello" in response.text
    print(f"[test] Index endpoint returned: {response.text}")


def test_status_endpoint():
    """Test the status endpoint."""
    response = requests.get(f"{APP_URL}/status")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    print(f"[test] Status endpoint returned: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
