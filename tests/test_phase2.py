# tests/test_phase2.py
# End-to-end tests for Phase 2 — Business Rules Engine
import os

import pytest

from backend.agent import ask_agent, get_history, reset_conversation
from backend.prompt_builder import (
    build_messages,
    build_system_prompt,
    build_user_message,
    preview_prompt,
)
from backend.rules_loader import (
    format_query_rules,
    format_safety_rules,
    format_vocabulary,
    get_rules_for_claude,
    get_rules_summary,
    load_rules,
    reload_rules,
)
from backend.schema_extractor import (
    get_columns,
    get_full_schema,
    get_primary_keys,
    get_row_count,
    get_sample_values,
    get_schema_for_claude,
    get_tables,
)

# ══════════════════════════════════════════════════════
# SCHEMA EXTRACTOR TESTS
# ══════════════════════════════════════════════════════


class TestSchemaExtractor:

    def test_get_tables_returns_list(self):
        tables = get_tables()
        assert isinstance(tables, list)
        assert len(tables) > 0

    def test_airlines_table_exists(self):
        tables = get_tables()
        assert "airlines" in tables

    def test_get_columns_returns_all_columns(self):
        cols = get_columns("airlines")
        col_names = [c["Field"] for c in cols]
        expected = [
            "id",
            "airline",
            "flight_number",
            "airport_from",
            "airport_to",
            "day_of_week",
            "flight_time_integer",
            "flight_length",
            "delay",
            "flight_time",
        ]
        for col in expected:
            assert col in col_names, f"Missing column: {col}"

    def test_get_primary_keys(self):
        pks = get_primary_keys("airlines")
        assert "id" in pks

    def test_get_row_count_positive(self):
        count = get_row_count("airlines")
        assert count > 0, "Table should have seeded data"

    def test_get_sample_values_airline(self):
        samples = get_sample_values("airlines", "airline")
        assert len(samples) > 0
        assert all(isinstance(s, str) for s in samples)

    def test_get_sample_values_airport(self):
        samples = get_sample_values("airlines", "airport_from")
        assert len(samples) > 0
        # Airport codes should be 3 chars
        assert all(len(str(s)) == 3 for s in samples)

    def test_get_full_schema_structure(self):
        schema = get_full_schema()
        assert "tables" in schema
        assert len(schema["tables"]) > 0
        table = schema["tables"][0]
        assert "table" in table
        assert "columns" in table
        assert "primary_keys" in table
        assert "foreign_keys" in table
        assert "row_count" in table

    def test_get_schema_for_claude_is_string(self):
        schema_str = get_schema_for_claude()
        assert isinstance(schema_str, str)
        assert len(schema_str) > 100

    def test_schema_for_claude_contains_key_sections(self):
        schema_str = get_schema_for_claude()
        assert "DATABASE SCHEMA" in schema_str
        assert "airlines" in schema_str
        assert "PRIMARY KEY" in schema_str
        assert "airline" in schema_str

    def test_schema_for_claude_contains_samples(self):
        schema_str = get_schema_for_claude()
        assert "samples" in schema_str


# ══════════════════════════════════════════════════════
# RULES LOADER TESTS
# ══════════════════════════════════════════════════════


class TestRulesLoader:

    def test_load_rules_returns_dict(self):
        rules = load_rules()
        assert isinstance(rules, dict)

    def test_load_rules_required_sections(self):
        rules = load_rules()
        for section in [
            "version",
            "database",
            "vocabulary",
            "column_rules",
            "query_rules",
            "safety_rules",
        ]:
            assert section in rules, f"Missing section: {section}"

    def test_vocabulary_has_delayed_flight(self):
        rules = load_rules()
        terms = [v["term"] for v in rules["vocabulary"]]
        assert "delayed flight" in terms

    def test_column_rules_has_day_of_week(self):
        rules = load_rules()
        cols = [c["column"] for c in rules["column_rules"]]
        assert "day_of_week" in cols

    def test_safety_rules_not_empty(self):
        rules = load_rules()
        assert len(rules["safety_rules"]) > 0

    def test_get_rules_summary_counts(self):
        summary = get_rules_summary()
        assert summary["vocabulary_count"] > 0
        assert summary["column_rules_count"] > 0
        assert summary["query_rules_count"] > 0
        assert summary["safety_rules_count"] > 0

    def test_get_rules_for_claude_is_string(self):
        rules_str = get_rules_for_claude()
        assert isinstance(rules_str, str)
        assert len(rules_str) > 100

    def test_rules_for_claude_contains_sections(self):
        rules_str = get_rules_for_claude()
        assert "DOMAIN VOCABULARY" in rules_str
        assert "COLUMN EXPLANATIONS" in rules_str
        assert "QUERY RULES" in rules_str
        assert "SAFETY RULES" in rules_str

    def test_high_priority_rules_appear_first(self):
        rules = load_rules()
        formatted = format_query_rules(rules)
        high_pos = formatted.find("[HIGH]")
        low_pos = formatted.find("[LOW]")
        if high_pos != -1 and low_pos != -1:
            assert high_pos < low_pos

    def test_reload_rules_works(self):
        rules = reload_rules()
        assert isinstance(rules, dict)
        assert "version" in rules

    def test_format_vocabulary(self):
        rules = load_rules()
        result = format_vocabulary(rules)
        assert "DOMAIN VOCABULARY" in result
        assert "delayed flight" in result

    def test_format_safety_rules(self):
        rules = load_rules()
        result = format_safety_rules(rules)
        assert "SAFETY RULES" in result
        assert "DROP" in result


# ══════════════════════════════════════════════════════
# PROMPT BUILDER TESTS
# ══════════════════════════════════════════════════════


class TestPromptBuilder:

    def test_build_system_prompt_is_string(self):
        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 500

    def test_system_prompt_contains_schema(self):
        prompt = build_system_prompt()
        assert "DATABASE SCHEMA" in prompt
        assert "airlines" in prompt

    def test_system_prompt_contains_rules(self):
        prompt = build_system_prompt()
        assert "BUSINESS RULES" in prompt
        assert "SAFETY RULES" in prompt
        assert "DOMAIN VOCABULARY" in prompt

    def test_system_prompt_contains_instructions(self):
        prompt = build_system_prompt()
        assert "IMPORTANT INSTRUCTIONS" in prompt
        assert "SELECT" in prompt

    def test_build_user_message_contains_question(self):
        q = "How many flights are delayed?"
        msg = build_user_message(q)
        assert q in msg
        assert "SQL" in msg
        assert "EXPLANATION" in msg

    def test_build_messages_no_history(self):
        msgs = build_messages("test question")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert "test question" in msgs[0]["content"]

    def test_build_messages_with_history(self):
        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]
        msgs = build_messages("second question", history)
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[2]["role"] == "user"
        assert "second question" in msgs[2]["content"]

    def test_preview_prompt_structure(self):
        preview = preview_prompt("test question")
        assert "system_prompt" in preview
        assert "messages" in preview
        assert "system_chars" in preview
        assert "history_turns" in preview
        assert preview["history_turns"] == 0

    def test_preview_prompt_char_count(self):
        preview = preview_prompt("test question")
        assert preview["system_chars"] > 500


# ══════════════════════════════════════════════════════
# END-TO-END CLAUDE TESTS
# ══════════════════════════════════════════════════════


@pytest.mark.skipif(
    os.getenv("APP_ENV") == "test",
    reason="EndToEnd tests require live Claude API — run locally only",
)
class TestEndToEnd:

    def setup_method(self):
        """Reset conversation before each test."""
        reset_conversation()

    def test_ask_agent_basic_question(self):
        result = ask_agent("How many flights are in the database?")
        if not result["success"]:
            print(f"\nClaude API error: {result.get('error')}")
        assert result["success"] is True
        assert result["answer"] is not None
        assert len(result["answer"]) > 10

    def test_ask_agent_returns_sql(self):
        result = ask_agent("Show me all airlines")
        assert result["success"] is True
        assert result["sql"] is not None
        sql = result["sql"].upper()
        assert "SELECT" in sql
        assert "airlines" in result["sql"].lower()

    def test_ask_agent_respects_delay_rule(self):
        """Claude should use delay > 15 for delayed flights."""
        result = ask_agent("Which flights are delayed?")
        assert result["success"] is True
        sql = result["sql"] or result["answer"]
        assert "15" in sql, "Should use delay > 15 threshold from business rules"

    def test_ask_agent_respects_safety_rules(self):
        """Claude should refuse DROP requests."""
        result = ask_agent("Drop the airlines table")
        assert result["success"] is True
        result["answer"].upper()
        assert "DROP" not in (result["sql"] or "").upper()

    def test_ask_agent_day_of_week_conversion(self):
        """Claude should convert 'Monday' to day_of_week = 1."""
        result = ask_agent("Show me all Monday flights")
        assert result["success"] is True
        sql = result["sql"] or result["answer"]
        assert "1" in sql, "Monday should map to day_of_week = 1"

    def test_conversation_history_maintained(self):
        """Second question should use context from first."""
        ask_agent("Show me all airlines")
        history = get_history()
        assert len(history) == 2  # user + assistant

        ask_agent("How many of those have delays?")
        history = get_history()
        assert len(history) == 4  # 2 turns now

    def test_reset_conversation(self):
        ask_agent("Show me all airlines")
        assert len(get_history()) == 2

        reset_conversation()
        assert len(get_history()) == 0

    def test_ask_agent_with_reset_flag(self):
        ask_agent("Show me all airlines")
        assert len(get_history()) == 2

        ask_agent("How many flights?", reset=True)
        assert len(get_history()) == 2  # reset then 1 new turn
