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


def get_row_count(table: str) -> int:
    """Get total number of rows in a table."""
    result = execute_query(f"SELECT COUNT(*) as total FROM `{table}`")
    if not result["success"] or not result["rows"]:
        return 0
    return result["rows"][0]["total"] or 0


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
# backend/schema_extractor.py
# Extracts rich schema context from MySQL for Claude

from backend.db import execute_query


# ── Table List ─────────────────────────────────────────

def get_tables() -> list:
    """Get all table names in the database."""
    result = execute_query("SHOW TABLES")
    if not result["success"]:
        return []
    return [list(row.values())[0] for row in result["rows"]]


# ── Columns ────────────────────────────────────────────

def get_columns(table: str) -> list:
    """Get full column details for a table."""
    result = execute_query(f"DESCRIBE `{table}`")
    if not result["success"]:
        return []
    return result["rows"]  # Field, Type, Null, Key, Default, Extra


# ── Primary Keys ───────────────────────────────────────

def get_primary_keys(table: str) -> list:
    """Return list of primary key column names."""
    cols = get_columns(table)
    return [c["Field"] for c in cols if c.get("Key") == "PRI"]


# ── Foreign Keys ───────────────────────────────────────

def get_foreign_keys(table: str) -> list:
    """Get foreign key relationships for a table."""
    sql = """
        SELECT
            COLUMN_NAME        AS column_name,
            REFERENCED_TABLE_NAME  AS referenced_table,
            REFERENCED_COLUMN_NAME AS referenced_column
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
    """
    result = execute_query(sql, (table,))
    if not result["success"]:
        return []
    return result["rows"]


# ── Indexes ────────────────────────────────────────────

def get_indexes(table: str) -> list:
    """Get index info for a table."""
    result = execute_query(f"SHOW INDEX FROM `{table}`")
    if not result["success"]:
        return []
    return [
        {
            "index_name": row["Key_name"],
            "column":     row["Column_name"],
            "unique":     row["Non_unique"] == 0,
        }
        for row in result["rows"]
    ]


# ── Row Count ──────────────────────────────────────────

def get_row_count(table: str) -> int:
    """Approximate row count (fast, uses MySQL stats)."""
    sql = """
        SELECT TABLE_ROWS
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
    """
    result = execute_query(sql, (table,))
    if not result["success"] or not result["rows"]:
        return 0
    return result["rows"][0]["TABLE_ROWS"] or 0


# ── Sample Values ──────────────────────────────────────

def get_sample_values(table: str, column: str, limit: int = 5) -> list:
    """Get distinct non-null sample values for a column."""
    sql = f"""
        SELECT DISTINCT `{column}`
        FROM `{table}`
        WHERE `{column}` IS NOT NULL
        LIMIT {limit}
    """
    result = execute_query(sql)
    if not result["success"]:
        return []
    return [list(row.values())[0] for row in result["rows"]]


# ── Full Schema for One Table ──────────────────────────

def get_table_schema(table: str) -> dict:
    """Assemble full rich schema for a single table."""
    columns = get_columns(table)

    # Enrich columns with sample values
    enriched_cols = []
    for col in columns:
        col_name = col["Field"]
        col_type = col.get("Type", "")

        # Only sample text/enum-like columns (skip blobs, large text)
        should_sample = any(t in col_type.lower() for t in [
            "char", "varchar", "enum", "text", "tinyint"
        ])

        enriched_cols.append({
            "name":          col_name,
            "type":          col_type,
            "nullable":      col.get("Null") == "YES",
            "key":           col.get("Key", ""),
            "default":       col.get("Default"),
            "extra":         col.get("Extra", ""),
            "sample_values": get_sample_values(table, col_name) if should_sample else [],
        })

    return {
        "table":        table,
        "row_count":    get_row_count(table),
        "columns":      enriched_cols,
        "primary_keys": get_primary_keys(table),
        "foreign_keys": get_foreign_keys(table),
        "indexes":      get_indexes(table),
    }


# ── Full DB Schema ─────────────────────────────────────

def get_full_schema() -> dict:
    """Get rich schema for all tables in the database."""
    tables = get_tables()
    return {
        "tables": [get_table_schema(t) for t in tables]
    }


# ── Claude-Formatted Schema ────────────────────────────

def get_schema_for_claude() -> str:
    """
    Format the full schema as clean text for Claude's prompt.
    Includes tables, columns, keys, relationships, and samples.
    """
    schema = get_full_schema()
    lines = ["DATABASE SCHEMA:", "=" * 50]

    for tbl in schema["tables"]:
        lines.append(f"\nTABLE: {tbl['table']}  (~{tbl['row_count']:,} rows)")
        lines.append("-" * 40)

        # Columns
        lines.append("COLUMNS:")
        for col in tbl["columns"]:
            flags = []
            if col["key"] == "PRI":
                flags.append("PRIMARY KEY")
            if col["key"] == "MUL":
                flags.append("INDEXED")
            if not col["nullable"]:
                flags.append("NOT NULL")
            if col["extra"]:
                flags.append(col["extra"].upper())

            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            lines.append(f"  {col['name']}  {col['type']}{flag_str}")

            if col["sample_values"]:
                samples = ", ".join(str(v) for v in col["sample_values"])
                lines.append(f"    → samples: {samples}")

        # Primary keys
        if tbl["primary_keys"]:
            lines.append(f"\nPRIMARY KEY: {', '.join(tbl['primary_keys'])}")

        # Foreign keys
        if tbl["foreign_keys"]:
            lines.append("FOREIGN KEYS:")
            for fk in tbl["foreign_keys"]:
                lines.append(
                    f"  {fk['column_name']} → "
                    f"{fk['referenced_table']}.{fk['referenced_column']}"
                )

        # Indexes
        non_pk_indexes = [i for i in tbl["indexes"] if i["index_name"] != "PRIMARY"]
        if non_pk_indexes:
            lines.append("INDEXES:")
            for idx in non_pk_indexes:
                unique = "UNIQUE " if idx["unique"] else ""
                lines.append(f"  {unique}{idx['index_name']} on {idx['column']}")

        lines.append("")

    return "\n".join(lines)