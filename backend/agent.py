# Claude AI logic — builds prompts, calls API, returns SQL
# Claude AI logic — builds prompts, calls API, returns SQL

import anthropic
from backend.config import get_settings
from backend.schema_extractor import get_schema_for_claude
from backend.rules import get_rules_for_claude

settings = get_settings()

# Initialize Anthropic client once
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Store conversation history for multi-turn chat
conversation_history = []


def build_system_prompt() -> str:
    """
    Build the full system prompt by combining:
    - Agent role & instructions
    - Live database schema
    - Business rules
    """
    schema = get_schema_for_claude()
    rules  = get_rules_for_claude()

    system_prompt = f"""You are an expert SQL AI Agent with deep knowledge 
of the user's specific MySQL database, business rules, and context.

## YOUR ROLE
- Convert natural language questions into accurate MySQL queries
- Always apply the business rules and schema below — never ignore them
- Use EXACT table and column names from the schema
- Apply business definitions strictly (e.g. "active airline", "revenue")
- Explain your queries clearly so the user can learn

## RESPONSE FORMAT
Always respond in this exact structure:

**Understanding:** (restate what the user is asking in 1 line)

**SQL Query:**
```sql
-- your query here with comments explaining key decisions
```

**Explanation:** (explain what the query does in plain English)

**Business Rules Applied:** (list which rules you used)

**Performance Notes:** (any index or optimization tips)

{schema}

{rules}

## IMPORTANT RULES
- Use backticks around table and column names
- Always add a LIMIT if not specified by user
- Add inline SQL comments for complex logic
- If a question is ambiguous, state your assumption
- If a query could be dangerous, warn the user
- Current dialect: MySQL 8.3
"""
    return system_prompt


def ask_agent(user_question: str, reset_history: bool = False) -> dict:
    """
    Main function — send a question to Claude and get SQL back.

    Args:
        user_question: The natural language question from user
        reset_history: If True, start a fresh conversation

    Returns:
        dict with success, answer, and conversation history
    """
    global conversation_history

    # Reset history if requested
    if reset_history:
        conversation_history = []

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_question
    })

    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=build_system_prompt(),
            messages=conversation_history
        )

        # Extract response text
        answer = response.content[0].text

        # Add Claude's response to history
        # (enables multi-turn conversation)
        conversation_history.append({
            "role": "assistant",
            "content": answer
        })

        return {
            "success":  True,
            "answer":   answer,
            "history_length": len(conversation_history)
        }

    except Exception as e:
        # Remove the failed user message from history
        conversation_history.pop()
        return {
            "success": False,
            "error":   str(e),
            "answer":  None
        }


def reset_conversation():
    """Clear conversation history — start fresh."""
    global conversation_history
    conversation_history = []
    return {"success": True, "message": "Conversation reset."}


def get_history() -> list:
    """Return current conversation history."""
    return conversation_history