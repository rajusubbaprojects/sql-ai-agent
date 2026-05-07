"""Phase 1 end-to-end test script — validates config, DB, schema, rules, agent, and API.

Run: python3 test_phase1.py
"""

import sys

import requests

BASE_URL = "http://localhost:8000"
passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    """Print a PASS or FAIL result and update global counters.

    Args:
        name: Human-readable test name.
        condition: True for pass, False for fail.
        detail: Optional extra context appended to FAIL lines.
    """
    global passed, failed
    if condition:
        print(f"  ✅ PASS — {name}")
        passed += 1
    else:
        print(f"  ❌ FAIL — {name} {detail}")
        failed += 1


def section(title: str):
    """Print a visually distinct section header.

    Args:
        title: Section title to display.
    """
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


# ── Test 1: Config ─────────────────────────────────────
section("TEST 1: Config")
try:
    from backend.config import get_settings

    s = get_settings()
    test("API key loaded", bool(s.anthropic_api_key))
    test("DB name loaded", bool(s.db_name))
    test("DB user loaded", bool(s.db_user))
    test("App env loaded", bool(s.app_env))
    test("Rules file set", bool(s.rules_file))
except Exception as e:
    test("Config import", False, str(e))


# ── Test 2: Database ───────────────────────────────────
section("TEST 2: Database")
try:
    from backend.db import execute_query, test_connection

    test("DB connection", test_connection())

    result = execute_query("SELECT 1 AS test")
    test("Simple query", result["success"])
    test("Returns rows", result["row_count"] == 1)

    result = execute_query("SHOW TABLES")
    test("Show tables", result["success"])
    test("Has tables", result["row_count"] >= 1)
except Exception as e:
    test("DB import", False, str(e))


# ── Test 3: Schema Extractor ───────────────────────────
section("TEST 3: Schema Extractor")
try:
    from backend.schema_extractor import get_schema_for_claude, get_table_columns, get_tables

    tables = get_tables()
    test("Tables found", len(tables) >= 1)
    test("Airlines exists", "airlines" in tables)

    cols = get_table_columns("airlines")
    test("Columns found", len(cols) >= 1)
    test("Has id column", any(c["Field"] == "id" for c in cols))
    test("Has delay column", any(c["Field"] == "delay" for c in cols))

    schema = get_schema_for_claude()
    test("Schema formatted", "DATABASE SCHEMA" in schema)
    test("Table in schema", "airlines" in schema)
except Exception as e:
    test("Schema import", False, str(e))


# ── Test 4: Business Rules ─────────────────────────────
section("TEST 4: Business Rules")
try:
    from backend.rules import get_rules_for_claude, load_rules

    rules = load_rules()
    test("Rules file loads", bool(rules))
    test("Has definitions", "definitions" in rules)
    test("Has query_rules", "query_rules" in rules)

    formatted = get_rules_for_claude()
    test("Rules formatted", "BUSINESS RULES" in formatted)
    test("Definitions in output", "DEFINITIONS" in formatted)
except Exception as e:
    test("Rules import", False, str(e))


# ── Test 5: Claude AI Agent ────────────────────────────
section("TEST 5: Claude AI Agent")
try:
    from backend.agent import ask_agent, reset_conversation

    reset_conversation()
    result = ask_agent("How many columns does the airlines table have?")
    test("Agent responds", result["success"])
    test("Has answer", bool(result.get("answer")))
    test("History increments", result["history_length"] == 2)

    # Follow-up — tests multi-turn memory
    result2 = ask_agent("What is the primary key of that table?")
    test("Follow-up works", result2["success"])
    test("History grows", result2["history_length"] == 4)
except Exception as e:
    test("Agent import", False, str(e))


# ── Test 6: API Endpoints ──────────────────────────────
section("TEST 6: API Endpoints")
try:
    # Root
    r = requests.get(f"{BASE_URL}/")
    test("GET /", r.status_code == 200)
    test("Returns status", r.json().get("status") == "online")

    # Health
    r = requests.get(f"{BASE_URL}/health")
    test("GET /health", r.status_code == 200)
    test("DB connected", r.json().get("database") == "connected")

    # Schema
    r = requests.get(f"{BASE_URL}/schema")
    test("GET /schema", r.status_code == 200)
    test("Schema returned", "schema" in r.json())

    # Rules
    r = requests.get(f"{BASE_URL}/rules")
    test("GET /rules", r.status_code == 200)
    test("Rules returned", "rules" in r.json())

    # History
    r = requests.get(f"{BASE_URL}/history")
    test("GET /history", r.status_code == 200)

    # Reset
    r = requests.post(f"{BASE_URL}/reset")
    test("POST /reset", r.status_code == 200)

except requests.exceptions.ConnectionError:
    test("API server running", False, "→ Is uvicorn running? Start it first!")


# ── Test 7: Full Flow ──────────────────────────────────
section("TEST 7: Full Flow (Natural Language → SQL)")
try:
    # Reset first
    requests.post(f"{BASE_URL}/reset")

    # Ask a question
    r = requests.post(
        f"{BASE_URL}/ask", json={"question": "Show me the top 5 most delayed flights"}
    )
    test("POST /ask works", r.status_code == 200)

    data = r.json()
    test("Got answer", bool(data.get("answer")))
    test("Answer has SQL", "```sql" in data.get("answer", ""))
    test("Business rules", "LIMIT" in data.get("answer", "").upper())

    # Follow-up conversation
    r2 = requests.post(
        f"{BASE_URL}/ask",
        json={"question": "Now show me only domestic flights from that result"},
    )
    test("Follow-up via API", r2.status_code == 200)
    test("History maintained", r2.json().get("history_length", 0) > 2)

    # Run the actual query
    r3 = requests.post(
        f"{BASE_URL}/query",
        json={
            "query": "SELECT airline, delay FROM airlines WHERE delay > 0 ORDER BY delay DESC LIMIT 5"
        },
    )
    test("POST /query works", r3.status_code == 200)
    test("Query returns data", "rows" in r3.json())

except Exception as e:
    test("Full flow", False, str(e))


# ── Summary ────────────────────────────────────────────
print(f"\n{'═' * 50}")
print("  PHASE 1 TEST RESULTS")
print(f"{'═' * 50}")
print(f"  ✅ Passed : {passed}")
print(f"  ❌ Failed : {failed}")
print(f"  Total    : {passed + failed}")
print(f"{'═' * 50}")

if failed == 0:
    print("  🎉 ALL TESTS PASSED — Ready for Phase 2!")
else:
    print(f"  ⚠️  Fix {failed} failing test(s) before Phase 2")

print()
sys.exit(0 if failed == 0 else 1)
