"""Prompt construction helpers — builds the system prompt and user message for Claude."""

from backend.rules_loader import get_rules_for_claude
from backend.schema_extractor import get_schema_for_claude

# ── System Prompt ──────────────────────────────────────


def build_system_prompt(schema: str = None, db_name: str = "airlines_db") -> str:
    """Build the system prompt injected at the start of every Claude conversation.

    Args:
        schema: Pre-fetched schema string. When None, auto-loads from the
            default database via get_schema_for_claude().
        db_name: Database name used to load the correct business rules.

    Returns:
        Fully assembled system prompt string.
    """
    if schema is None:
        schema = get_schema_for_claude()

    rules = get_rules_for_claude(db_name=db_name)

    return f"""You are an expert SQL assistant for a MySQL database.
Your job is to help users query the database using natural language.
You have deep knowledge of the database schema and must follow all
business rules exactly when generating SQL queries.

{schema}

{rules}

IMPORTANT INSTRUCTIONS:
- Only generate SELECT queries unless explicitly told otherwise
- Always follow the safety rules — never DROP, TRUNCATE, ALTER, INSERT, UPDATE or DELETE
- When unsure about intent, state your assumption clearly before the SQL
- If a question cannot be answered from this database, say so politely
- Always produce valid MySQL syntax
"""


# ── User Message ───────────────────────────────────────


def build_user_message(question: str) -> str:
    """Wrap a user question in the structured prompt format Claude expects."""
    return f"""Please answer this question about the database:

{question}

You MUST respond in exactly this format:

```sql
YOUR_SQL_QUERY_HERE
```

EXPLANATION: <plain English explanation of what the query does>
ASSUMPTIONS: <any assumptions you made, if applicable>

Rules:
- The SQL block is mandatory — always include it
- Only use SELECT statements
- Use valid MySQL syntax
- If the question cannot be answered from this database, still respond with:
```sql
SELECT 'Unable to answer: <reason>' AS message;
```
"""


# ── Conversation History ───────────────────────────────


def build_messages(question: str, history: list = None) -> list:
    """Build the full messages array for a Claude API call."""
    messages = []
    if history:
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": build_user_message(question)})
    return messages


# ── Prompt Preview ─────────────────────────────────────


def preview_prompt(question: str, history: list = None) -> dict:
    """Return all prompt components for debugging or inspection."""
    return {
        "system_prompt": build_system_prompt(),
        "messages": build_messages(question, history),
        "system_chars": len(build_system_prompt()),
        "question": question,
        "history_turns": len(history) if history else 0,
    }
