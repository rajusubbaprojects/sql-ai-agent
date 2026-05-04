# Auto-reads MySQL schema and formats it for Claude
# Auto-reads MySQL schema and formats it for Claude

from backend.db import execute_query


def get_tables() -> list:
    """Get all table names in the database."""
    result = execute_query("SHOW TABLES")
    if not result["success"]:
        return []
    return [list(row.values())[0] for row in result["rows"]]


def get_table_columns(table_name: str) -> list:
    """Get all columns for a specific table."""
    result = execute_query(f"DESCRIBE `{table_name}`")
    if not result["success"]:
        return []
    return result["rows"]


def get_table_indexes(table_name: str) -> list:
    """Get indexes for a specific table."""
    result = execute_query(f"SHOW INDEX FROM `{table_name}`")
    if not result["success"]:
        return []
    return result["rows"]


def get_sample_data(table_name: str, limit: int = 3) -> list:
    """Get sample rows from a table so Claude understands the data."""
    result = execute_query(f"SELECT * FROM `{table_name}` LIMIT {limit}")
    if not result["success"]:
        return []
    return result["rows"]


def get_row_count(table_name: str) -> int:
    """Get total number of rows in a table."""
    result = execute_query(f"SELECT COUNT(*) as total FROM `{table_name}`")
    if not result["success"]:
        return 0
    return result["rows"][0]["total"]


def extract_full_schema() -> dict:
    """
    Extract the complete database schema.
    Returns a structured dict with all tables, columns,
    indexes, sample data and row counts.
    """
    tables = get_tables()
    schema = {}

    for table in tables:
        columns  = get_table_columns(table)
        indexes  = get_table_indexes(table)
        sample   = get_sample_data(table)
        rowcount = get_row_count(table)

        schema[table] = {
            "columns":    columns,
            "indexes":    indexes,
            "sample":     sample,
            "row_count":  rowcount
        }

    return schema


def format_schema_for_claude(schema: dict) -> str:
    """
    Format the schema dict into clean text
    that Claude can easily understand.
    """
    if not schema:
        return "No schema available."

    lines = []
    lines.append("=== DATABASE SCHEMA ===\n")

    for table_name, info in schema.items():
        lines.append(f"TABLE: {table_name}")
        lines.append(f"Rows: {info['row_count']:,}")
        lines.append("-" * 40)

        # Columns
        lines.append("COLUMNS:")
        for col in info["columns"]:
            nullable = "NULL" if col.get("Null") == "YES" else "NOT NULL"
            key      = f" [{col.get('Key')}]" if col.get("Key") else ""
            default  = f" DEFAULT={col.get('Default')}" if col.get("Default") else ""
            lines.append(
                f"  {col['Field']:<25} {col['Type']:<20} {nullable}{key}{default}"
            )

        # Indexes
        if info["indexes"]:
            lines.append("\nINDEXES:")
            seen = set()
            for idx in info["indexes"]:
                idx_name = idx.get("Key_name")
                if idx_name not in seen:
                    seen.add(idx_name)
                    unique = "UNIQUE " if idx.get("Non_unique") == 0 else ""
                    lines.append(f"  {unique}{idx_name} → {idx.get('Column_name')}")

        # Sample data
        if info["sample"]:
            lines.append("\nSAMPLE DATA (3 rows):")
            for row in info["sample"]:
                lines.append(f"  {row}")

        lines.append("")  # blank line between tables

    return "\n".join(lines)


def get_schema_for_claude() -> str:
    """
    Main function called by agent.py.
    Returns formatted schema string ready to inject into Claude prompt.
    """
    schema = extract_full_schema()
    return format_schema_for_claude(schema)