# MySQL connection — connect, execute queries, return results
import mysql.connector
from mysql.connector import Error

from backend.config import get_settings

settings = get_settings()

# ── Known databases ────────────────────────────────────────────────────────────
# Add new database names here as you onboard them.
AVAILABLE_DATABASES = ["airlines_db", "sakila"]


def get_connection(db_name: str = None):
    """
    Create and return a database connection.
    If db_name is None, falls back to settings.db_name (airlines_db).
    """
    database = db_name or settings.db_name
    try:
        connection = mysql.connector.connect(
            host=settings.db_host,
            port=int(settings.db_port),
            database=database,
            user=settings.db_user,
            password=settings.db_password,
        )
        return connection
    except Error as e:
        print(f"The error '{e}' occurred")
        raise


def execute_query(sql: str, params: tuple = None, db_name: str = None) -> dict:
    """
    Execute a SQL query and return results.
    Pass db_name to run against a specific database.
    """
    try:
        conn = get_connection(db_name)
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute(sql, params)

        sql_stripped = sql.strip().upper()
        if sql_stripped.startswith(("INSERT", "UPDATE", "DELETE")):
            conn.commit()
            return {
                "success": True,
                "rows_affected": cursor.rowcount,
                "last_insert_id": cursor.lastrowid,
            }

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def test_connection(db_name: str = None) -> bool:
    """Quick check — is the database reachable."""
    try:
        conn = get_connection(db_name)
        if conn.is_connected():
            info = conn.get_server_info()
            db = db_name or settings.db_name
            print("Connected to MySQL Server version ", info)
            print(f"Database: {db}")
            conn.close()
            return True
    except Error as e:
        print(f"The error '{e}' occurred")
        return False
