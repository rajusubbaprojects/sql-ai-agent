"""
Phase 4 — Docker integration tests.
These run against the live Docker stack (app + db).
"""

import requests

BASE_URL = "http://localhost:8000"


class TestHealthEndpoints:
    def test_root_endpoint(self):
        r = requests.get(f"{BASE_URL}/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert data["app"] == "SQL AI Agent"
        assert data["version"] == "1.0.0"

    def test_health_endpoint(self):
        r = requests.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["ai"] == "ready"

    def test_health_response_time(self):
        """Health check must respond within 3 seconds."""
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        assert r.status_code == 200


class TestSchemaEndpoint:
    def test_schema_returns_data(self):
        r = requests.get(f"{BASE_URL}/schema")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "schema" in data
        assert len(data["schema"]) > 0

    def test_schema_contains_tables(self):
        r = requests.get(f"{BASE_URL}/schema")
        schema = r.json()["schema"]
        # airlines_db should have at least one table
        assert isinstance(schema, (str, dict, list))


class TestRulesEndpoint:
    def test_rules_returns_data(self):
        r = requests.get(f"{BASE_URL}/rules")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "rules" in data

    def test_add_rule(self):
        payload = {"category": "test", "rule": "This is a docker test rule"}
        r = requests.post(f"{BASE_URL}/rules", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True


class TestQueryEndpoint:
    def test_valid_query(self):
        payload = {"query": "SELECT 1 AS docker_test"}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True

    def test_empty_query_rejected(self):
        payload = {"query": ""}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 400

    def test_dangerous_query_blocked(self):
        payload = {"query": "DROP TABLE flights"}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 403


class TestHistoryEndpoints:
    def test_get_history(self):
        r = requests.get(f"{BASE_URL}/history")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "history" in data

    def test_reset_history(self):
        r = requests.post(f"{BASE_URL}/reset")
        assert r.status_code == 200
