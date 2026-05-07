"""Business rules loader — reads, validates, and formats business rules YAML for Claude."""

import os

import yaml

# ── Rules file paths per database ──────────────────────────────────────────────

_BASE = os.path.dirname(__file__)

RULES_FILES = {
    "airlines_db": os.path.join(_BASE, "configs", "business_rules_airlines.yaml"),
    "sakila": os.path.join(_BASE, "configs", "business_rules_sakila.yaml"),
}

# Backward-compat alias
RULES_FILE = RULES_FILES["airlines_db"]


# ── Load & Validate ────────────────────────────────────


def load_rules(db_name: str = "airlines_db") -> dict:
    """Load and validate the rules YAML for a given database.

    Args:
        db_name: Which database's rules to load. Defaults to airlines_db.

    Returns:
        Parsed YAML content as a dict.

    Raises:
        FileNotFoundError: If the rules file does not exist.
        ValueError: If required sections are missing.
    """
    rules_file = RULES_FILES.get(db_name, RULES_FILES["airlines_db"])

    if not os.path.exists(rules_file):
        raise FileNotFoundError(f"Business rules file not found: {rules_file}")

    with open(rules_file, "r") as f:
        rules = yaml.safe_load(f)

    _validate_rules(rules)
    return rules


def _validate_rules(rules: dict) -> None:
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
        raise ValueError(f"business_rules YAML missing sections: {missing}")


# ── Section Formatters ─────────────────────────────────


def format_vocabulary(rules: dict) -> str:
    lines = ["DOMAIN VOCABULARY:", "-" * 40]
    for item in rules.get("vocabulary", []):
        lines.append(f"• '{item['term']}' means: {item['definition']}")
        if "sql_hint" in item:
            lines.append(f"  SQL: {item['sql_hint']}")
    return "\n".join(lines)


def format_column_rules(rules: dict) -> str:
    lines = ["COLUMN EXPLANATIONS:", "-" * 40]
    for item in rules.get("column_rules", []):
        lines.append(f"• {item['column']}: {item['explanation']}")
        if "example" in item:
            lines.append(f"  Example: {item['example']}")
    return "\n".join(lines)


def format_query_rules(rules: dict) -> str:
    query_rules = rules.get("query_rules", [])
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
    lines = ["SAFETY RULES (never violate):", "-" * 40]
    for item in rules.get("safety_rules", []):
        lines.append(f"• {item['rule']}")
    return "\n".join(lines)


def format_output_rules(rules: dict) -> str:
    lines = ["OUTPUT FORMAT RULES:", "-" * 40]
    for item in rules.get("output_rules", []):
        lines.append(f"• {item['rule']}")
    return "\n".join(lines)


# ── Main Formatter ─────────────────────────────────────


def get_rules_for_claude(db_name: str = "airlines_db") -> str:
    """Assemble and return all business rules as a single prompt-ready string.

    Args:
        db_name: Which database's rules to load.

    Returns:
        Concatenated sections ready to inject into Claude's system prompt.
    """
    rules = load_rules(db_name)

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


def reload_rules(db_name: str = "airlines_db") -> dict:
    """Force-reload rules from disk (useful for hot-reload without restart)."""
    return load_rules(db_name)


# ── Rule Introspection ─────────────────────────────────


def get_rules_summary(db_name: str = "airlines_db") -> dict:
    """Return a summary of loaded rules with counts per section."""
    rules = load_rules(db_name)
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
