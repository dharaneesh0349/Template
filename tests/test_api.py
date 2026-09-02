import pytest
from fastapi.testclient import TestClient
from fastapi_backend import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CloudStack Template Automation" in data["service"]


def test_distributions_endpoint():
    response = client.get("/api/distributions")
    assert response.status_code == 200
    data = response.json()
    assert "rhel_derivatives" in data
    assert "debian_derivatives" in data


def test_hypervisors_endpoint():
    response = client.get("/api/hypervisors")
    assert response.status_code == 200
    data = response.json()
    assert "kvm" in data
    assert "xen" in data
    assert "vmware" in data


def test_ai_diagnose_rule_fallback():
    payload = {
        "execution_id": "test-execution-123",
        "step_name": "Cloud-init Installation",
        "command": "yum install -y cloud-init",
        "error_output": "No package cloud-init available."
    }
    response = client.post("/api/ai/diagnose", json=payload)
    assert response.status_code == 200
    diag = response.json()
    assert "EPEL" in diag["root_cause"] or "repository" in diag["root_cause"].lower()
    assert diag["can_auto_recover"] is True
    assert len(diag["remediation_commands"]) > 0


def test_docs_disabled():
    response = client.get("/docs")
    assert response.status_code == 404
    response_redoc = client.get("/redoc")
    assert response_redoc.status_code == 404
    response_openapi = client.get("/openapi.json")
    assert response_openapi.status_code == 404
