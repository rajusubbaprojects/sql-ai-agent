"""MySQL schema extraction helpers — queries metadata to build rich schema context for Claude."""

from backend.db import execute_query

# ── Table List ─────────────────────────────────────────


def get_tables(db_name: str = None) -> list:
    """Return all table names in the specified database.

    Args:
        db_name: Database to inspect. Defaults to settings.db_name.

    Returns:
        List of table name strings, or an empty list on error.
    """
    result = execute_query("SHOW TABLES", db_name=db_name)
    if not result["success"]:
        return []
    return [list(row.values())[0] for row in result["rows"]]


# ── Columns ────────────────────────────────────────────


def get_columns(table: str, db_name: str = None) -> list:
    """Return full column metadata for a table via DESCRIBE.

    Args:
        table: Table name to describe.
        db_name: Database containing the table.

    Returns:
        List of column descriptor dicts (Field, Type, Null, Key, Default,
        Extra), or an empty list on error.
    """
    result = execute_query(f"DESCRIBE `{table}`", db_name=db_name)
    if not result["success"]:
        return []
    return result["rows"]


# ── Primary Keys ───────────────────────────────────────


def get_primary_keys(table: str, db_name: str = None) -> list:
    """Return the primary key column names for a table.

    Args:
        table: Table name.
        db_name: Database containing the table.

    Returns:
        List of column name strings that form the primary key.
    """
    cols = get_columns(table, db_name)
    return [c["Field"] for c in cols if c.get("Key") == "PRI"]


# ── Foreign Keys ───────────────────────────────────────


def get_foreign_keys(table: str, db_name: str = None) -> list:
    """Return foreign key relationships for a table from information_schema.

    Args:
        table: Table name.
        db_name: Database containing the table. Defaults to "airlines_db".

    Returns:
        List of dicts with column_name, referenced_table, and
        referenced_column keys.
    """
    sql = """
        SELECT
            COLUMN_NAME            AS column_name,
            REFERENCED_TABLE_NAME  AS referenced_table,
            REFERENCED_COLUMN_NAME AS referenced_column
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
    """
    db = db_name or "airlines_db"
    result = execute_query(sql, (db, table), db_name=db_name)
    if not result["success"]:
        return []
    return result["rows"]


# ── Indexes ────────────────────────────────────────────


def get_indexes(table: str, db_name: str = None) -> list:
    """Return index metadata for a table.

    Args:
        table: Table name.
        db_name: Database containing the table.

    Returns:
        List of dicts with index_name, column, and unique keys.
    """
    result = execute_query(f"SHOW INDEX FROM `{table}`", db_name=db_name)
    if not result["success"]:
        return []
    return [
        {
            "index_name": row["Key_name"],
            "column": row["Column_name"],
            "unique": row["Non_unique"] == 0,
        }
        for row in result["rows"]
    ]


# ── Row Count ──────────────────────────────────────────


def get_row_count(table: str, db_name: str = None) -> int:
    """Return the total number of rows in a table.

    Args:
        table: Table name.
        db_name: Database containing the table.

    Returns:
        Row count as an integer, or 0 on error.
    """
    result = execute_query(f"SELECT COUNT(*) as total FROM `{table}`", db_name=db_name)
    if not result["success"] or not result["rows"]:
        return 0
    return result["rows"][0]["total"] or 0


# ── Sample Values ──────────────────────────────────────


def get_sample_values(table: str, column: str, limit: int = 5, db_name: str = None) -> list:
    """Return a small set of distinct non-null sample values for a column.

    Args:
        table: Table name.
        column: Column name to sample.
        limit: Maximum number of distinct values to return.
        db_name: Database containing the table.

    Returns:
        List of sample values (type depends on column type), or [] on error.
    """
    sql = f"""
        SELECT DISTINCT `{column}`
        FROM `{table}`
        WHERE `{column}` IS NOT NULL
        LIMIT {limit}
    """
    result = execute_query(sql, db_name=db_name)
    if not result["success"]:
        return []
    return [list(row.values())[0] for row in result["rows"]]


# ── Full Schema for One Table ──────────────────────────


def get_table_schema(table: str, db_name: str = None) -> dict:
    """Assemble a rich schema dict for a single table.

    Enriches column metadata with sample values for character-typed columns
    and joins in primary keys, foreign keys, and indexes.

    Args:
        table: Table name.
        db_name: Database containing the table.

    Returns:
        Dict with table, row_count, columns, primary_keys, foreign_keys,
        and indexes keys.
    """
    columns = get_columns(table, db_name)

    enriched_cols = []
    for col in columns:
        col_name = col["Field"]
        col_type = col.get("Type", "")

        should_sample = any(
            t in col_type.lower() for t in ["char", "varchar", "enum", "text", "tinyint"]
        )

        enriched_cols.append(
            {
                "name": col_name,
                "type": col_type,
                "nullable": col.get("Null") == "YES",
                "key": col.get("Key", ""),
                "default": col.get("Default"),
                "extra": col.get("Extra", ""),
                "sample_values": (
                    get_sample_values(table, col_name, db_name=db_name) if should_sample else []
                ),
            }
        )

    return {
        "table": table,
        "row_count": get_row_count(table, db_name),
        "columns": enriched_cols,
        "primary_keys": get_primary_keys(table, db_name),
        "foreign_keys": get_foreign_keys(table, db_name),
        "indexes": get_indexes(table, db_name),
    }


# ── Full DB Schema ─────────────────────────────────────


def get_full_schema(db_name: str = None) -> dict:
    """Build a rich schema dict covering every table in the database.

    Args:
        db_name: Database to inspect. Defaults to settings.db_name.

    Returns:
        Dict with a "tables" key containing a list of get_table_schema results.
    """
    tables = get_tables(db_name)
    return {"tables": [get_table_schema(t, db_name) for t in tables]}


# ── Claude-Formatted Schema ────────────────────────────


def get_schema_for_claude(db_name: str = None) -> str:
    """Format the full database schema as human-readable text for Claude's prompt.

    Args:
        db_name: Database to describe. Defaults to "airlines_db".

    Returns:
        Multi-line string with table names, column details, sample values,
        primary/foreign keys, and index information.
    """
    db_label = db_name or "airlines_db"
    schema = get_full_schema(db_name)
    lines = [f"DATABASE SCHEMA ({db_label}):", "=" * 50]

    for tbl in schema["tables"]:
        lines.append(f"\nTABLE: {tbl['table']}  (~{tbl['row_count']:,} rows)")
        lines.append("-" * 40)

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

        if tbl["primary_keys"]:
            lines.append(f"\nPRIMARY KEY: {', '.join(tbl['primary_keys'])}")

        if tbl["foreign_keys"]:
            lines.append("FOREIGN KEYS:")
            for fk in tbl["foreign_keys"]:
                lines.append(
                    f"  {fk['column_name']} → "
                    f"{fk['referenced_table']}.{fk['referenced_column']}"
                )

        non_pk_indexes = [i for i in tbl["indexes"] if i["index_name"] != "PRIMARY"]
        if non_pk_indexes:
            lines.append("INDEXES:")
            for idx in non_pk_indexes:
                unique = "UNIQUE " if idx["unique"] else ""
                lines.append(f"  {unique}{idx['index_name']} on {idx['column']}")

        lines.append("")

    return "\n".join(lines)
