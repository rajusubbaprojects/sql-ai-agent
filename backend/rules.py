# Business rules engine — loads and injects rules into prompts
# Business rules engine — loads and injects rules into prompts

from pathlib import Path

import yaml

from backend.config import get_settings

settings = get_settings()


def load_rules() -> dict:
    """
    Load business rules from rules.yaml file.
    Returns empty dict if file not found.
    """
    rules_path = Path(settings.rules_file)

    if not rules_path.exists():
        print(f"⚠️  Rules file not found: {rules_path}")
        return {}

    with open(rules_path, "r") as f:
        rules = yaml.safe_load(f)

    return rules or {}


def format_rules_for_claude(rules: dict) -> str:
    """
    Format rules dict into clean text
    that Claude can easily understand.
    """
    if not rules:
        return "No business rules defined."

    lines = []
    lines.append("=== BUSINESS RULES & CONTEXT ===\n")

    # Business Definitions
    if "definitions" in rules:
        lines.append("BUSINESS DEFINITIONS:")
        lines.append("(These terms have specific meanings in our system)")
        for item in rules["definitions"]:
            lines.append(f"  • {item['name']}: {item['rule']}")
        lines.append("")

    # Query Rules
    if "query_rules" in rules:
        lines.append("QUERY RULES:")
        lines.append("(Always follow these when writing SQL)")
        for rule in rules["query_rules"]:
            lines.append(f"  • {rule}")
        lines.append("")

    # Naming Conventions
    if "naming" in rules:
        lines.append("NAMING CONVENTIONS:")
        for rule in rules["naming"]:
            lines.append(f"  • {rule}")
        lines.append("")

    # Performance Rules
    if "performance" in rules:
        lines.append("PERFORMANCE RULES:")
        for rule in rules["performance"]:
            lines.append(f"  • {rule}")
        lines.append("")

    return "\n".join(lines)


def get_rules_for_claude() -> str:
    """
    Main function called by agent.py.
    Returns formatted rules string ready to inject into Claude prompt.
    """
    rules = load_rules()
    return format_rules_for_claude(rules)


def add_custom_rule(category: str, rule: str) -> bool:
    """
    Dynamically add a new rule to rules.yaml at runtime.
    Useful for when users define new rules via the API.
    """
    try:
        rules_path = Path(settings.rules_file)
        rules = load_rules()

        if category not in rules:
            rules[category] = []

        rules[category].append(rule)

        with open(rules_path, "w") as f:
            yaml.dump(rules, f, default_flow_style=False)

        return True
    except Exception as e:
        print(f"❌ Error adding rule: {e}")
        return False
