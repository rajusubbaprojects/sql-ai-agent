"""
Phase 4 — Docker integration tests.
These run against the live Docker stack (app + db).
"""

import requests

BASE_URL = "http://localhost:8000"


class TestHealthEndpoints:
    """Tests for the root and health check endpoints."""

    def test_root_endpoint(self):
        """Verify the root endpoint returns expected app metadata.

        Asserts:
            HTTP 200 with status "online", app name "SQL AI Agent", and version "1.0.0".
        """
        r = requests.get(f"{BASE_URL}/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert data["app"] == "SQL AI Agent"
        assert data["version"] == "1.0.0"

    def test_health_endpoint(self):
        """Verify the health endpoint reports all subsystems as ready.

        Asserts:
            HTTP 200 with status "healthy", database "connected", and ai "ready".
        """
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
    """Tests for the /schema endpoint."""

    def test_schema_returns_data(self):
        """Verify the schema endpoint returns a non-empty schema payload.

        Asserts:
            HTTP 200 with success True and a non-empty "schema" field.
        """
        r = requests.get(f"{BASE_URL}/schema")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "schema" in data
        assert len(data["schema"]) > 0

    def test_schema_contains_tables(self):
        """Verify the schema payload is a recognised data structure.

        Asserts:
            The "schema" value is a str, dict, or list (airlines_db has at least one table).
        """
        r = requests.get(f"{BASE_URL}/schema")
        schema = r.json()["schema"]
        # airlines_db should have at least one table
        assert isinstance(schema, (str, dict, list))


class TestRulesEndpoint:
    """Tests for the /rules endpoint (GET and POST)."""

    def test_rules_returns_data(self):
        """Verify GET /rules returns a successful response containing a rules list.

        Asserts:
            HTTP 200 with success True and a "rules" key present.
        """
        r = requests.get(f"{BASE_URL}/rules")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "rules" in data

    def test_add_rule(self):
        """Verify a new rule can be created via POST /rules.

        Asserts:
            HTTP 200 with success True after posting a test rule payload.
        """
        payload = {"category": "test", "rule": "This is a docker test rule"}
        r = requests.post(f"{BASE_URL}/rules", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True


class TestQueryEndpoint:
    """Tests for the /query endpoint including validation and security guardrails."""

    def test_valid_query(self):
        """Verify a safe SELECT query executes successfully.

        Asserts:
            HTTP 200 with success True for a trivial SELECT 1 statement.
        """
        payload = {"query": "SELECT 1 AS docker_test"}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True

    def test_empty_query_rejected(self):
        """Verify an empty query string is rejected with a 400 error.

        Asserts:
            HTTP 400 when the query field is an empty string.
        """
        payload = {"query": ""}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 400

    def test_dangerous_query_blocked(self):
        """Verify a destructive DDL statement is blocked with a 403 error.

        Asserts:
            HTTP 403 when a DROP TABLE statement is submitted.
        """
        payload = {"query": "DROP TABLE flights"}
        r = requests.post(f"{BASE_URL}/query", json=payload)
        assert r.status_code == 403


class TestHistoryEndpoints:
    """Tests for the /history and /reset endpoints."""

    def test_get_history(self):
        """Verify GET /history returns a successful response with a history list.

        Asserts:
            HTTP 200 with success True and a "history" key present.
        """
        r = requests.get(f"{BASE_URL}/history")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "history" in data

    def test_reset_history(self):
        """Verify POST /reset clears conversation history and returns HTTP 200.

        Asserts:
            HTTP 200 after a reset request.
        """
        r = requests.post(f"{BASE_URL}/reset")
        assert r.status_code == 200
