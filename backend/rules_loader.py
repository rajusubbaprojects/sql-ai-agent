"""Business rules loader — reads, validates, and formats business_rules.yaml for Claude."""

import os
from functools import lru_cache

import yaml

# ── Path to rules file ─────────────────────────────────

RULES_FILE = os.path.join(os.path.dirname(__file__), "configs", "business_rules.yaml")


# ── Load & Validate ────────────────────────────────────


@lru_cache(maxsize=1)
def load_rules() -> dict:
    """Load and validate business_rules.yaml, caching the result.

    Returns:
        Parsed YAML content as a dict.

    Raises:
        FileNotFoundError: If business_rules.yaml does not exist.
        ValueError: If required sections are missing from the file.
    """
    if not os.path.exists(RULES_FILE):
        raise FileNotFoundError(f"Business rules file not found: {RULES_FILE}")

    with open(RULES_FILE, "r") as f:
        rules = yaml.safe_load(f)

    _validate_rules(rules)
    return rules


def _validate_rules(rules: dict) -> None:
    """Assert all required top-level sections are present in the rules dict.

    Args:
        rules: Parsed YAML dict to validate.

    Raises:
        ValueError: If one or more required sections are absent.
    """
    required_sections = [
        "version",
        "database",
        "vocabulary",
        "column_rules",
        "query_rules",
        "safety_rules",
    ]
    missing = [s for s in required_sections if s not in rules]
    if missing:
        raise ValueError(f"business_rules.yaml missing sections: {missing}")


# ── Section Formatters ─────────────────────────────────


def format_vocabulary(rules: dict) -> str:
    """Format the vocabulary section for injection into Claude's prompt.

    Args:
        rules: Full parsed rules dict.

    Returns:
        Multi-line string with domain term definitions.
    """
    lines = ["DOMAIN VOCABULARY:", "-" * 40]
    for item in rules.get("vocabulary", []):
        lines.append(f"• '{item['term']}' means: {item['definition']}")
        if "sql_hint" in item:
            lines.append(f"  SQL: {item['sql_hint']}")
    return "\n".join(lines)


def format_column_rules(rules: dict) -> str:
    """Format the column_rules section for injection into Claude's prompt.

    Args:
        rules: Full parsed rules dict.

    Returns:
        Multi-line string with column explanations and examples.
    """
    lines = ["COLUMN EXPLANATIONS:", "-" * 40]
    for item in rules.get("column_rules", []):
        lines.append(f"• {item['column']}: {item['explanation']}")
        if "example" in item:
            lines.append(f"  Example: {item['example']}")
    return "\n".join(lines)


def format_query_rules(rules: dict) -> str:
    """Format query rules sorted by priority (high → medium → low).

    Args:
        rules: Full parsed rules dict.

    Returns:
        Multi-line string with prioritised query rules.
    """
    query_rules = rules.get("query_rules", [])

    # Sort by priority: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_rules = sorted(
        query_rules, key=lambda r: priority_order.get(r.get("priority", "low"), 2)
    )

    lines = ["QUERY RULES (follow strictly):", "-" * 40]
    for item in sorted_rules:
        priority = item.get("priority", "medium").upper()
        lines.append(f"• [{priority}] {item['rule']}")
    return "\n".join(lines)


def format_safety_rules(rules: dict) -> str:
    """Format safety rules for injection into Claude's prompt.

    Args:
        rules: Full parsed rules dict.

    Returns:
        Multi-line string listing safety constraints.
    """
    lines = ["SAFETY RULES (never violate):", "-" * 40]
    for item in rules.get("safety_rules", []):
        lines.append(f"• {item['rule']}")
    return "\n".join(lines)


def format_output_rules(rules: dict) -> str:
    """Format output formatting rules for injection into Claude's prompt.

    Args:
        rules: Full parsed rules dict.

    Returns:
        Multi-line string with output format instructions.
    """
    lines = ["OUTPUT FORMAT RULES:", "-" * 40]
    for item in rules.get("output_rules", []):
        lines.append(f"• {item['rule']}")
    return "\n".join(lines)


# ── Main Formatter ─────────────────────────────────────


def get_rules_for_claude() -> str:
    """Assemble and return all business rules as a single prompt-ready string.

    Returns:
        Concatenated sections: vocabulary, column rules, query rules,
        output rules, and safety rules.
    """
    rules = load_rules()

    sections = [
        f"BUSINESS RULES FOR: {rules['database']}",
        "=" * 50,
        f"Description: {rules['description']}",
        "",
        format_vocabulary(rules),
        "",
        format_column_rules(rules),
        "",
        format_query_rules(rules),
        "",
        format_output_rules(rules),
        "",
        format_safety_rules(rules),
    ]

    return "\n".join(sections)


# ── Reload Helper ──────────────────────────────────────


def reload_rules() -> dict:
    """Force-reload rules from disk by clearing the lru_cache.

    Useful for hot-reloading rule changes without a server restart.

    Returns:
        Freshly loaded rules dict.
    """
    load_rules.cache_clear()
    return load_rules()


# ── Rule Introspection ─────────────────────────────────


def get_rules_summary() -> dict:
    """Return a summary of loaded rules with counts per section.

    Returns:
        Dict with version, database, description, and *_count keys
        for each rules section.
    """
    rules = load_rules()
    return {
        "version": rules.get("version"),
        "database": rules.get("database"),
        "description": rules.get("description"),
        "vocabulary_count": len(rules.get("vocabulary", [])),
        "column_rules_count": len(rules.get("column_rules", [])),
        "query_rules_count": len(rules.get("query_rules", [])),
        "safety_rules_count": len(rules.get("safety_rules", [])),
        "output_rules_count": len(rules.get("output_rules", [])),
    }
