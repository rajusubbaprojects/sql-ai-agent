# MySQL connection — connect, execute queries, return results
import mysql.connector
from mysql.connector import Error

from backend.config import get_settings

settings = get_settings()


def get_connection():
    """Create and return a database connection object."""
    try:
        connection = mysql.connector.connect(
            host=settings.db_host,
            port=int(settings.db_port),
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )
        return connection
    except Error as e:
        print(f"The error '{e}' occurred")
        raise


def execute_query(sql: str, params: tuple = None) -> dict:
    """Execute a SQL query and return results."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute(sql, params)

        # DML statements (INSERT, UPDATE, DELETE) — commit and return affected rows
        sql_stripped = sql.strip().upper()
        if sql_stripped.startswith(("INSERT", "UPDATE", "DELETE")):
            conn.commit()
            return {
                "success": True,
                "rows_affected": cursor.rowcount,
                "last_insert_id": cursor.lastrowid,
            }

        # SELECT / DESCRIBE / SHOW — fetch results
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


def test_connection() -> bool:
    # Quick check - is the database reachable
    try:
        conn = get_connection()
        if conn.is_connected():
            info = conn.get_server_info()
            print("Connected to MySQL Server version ", info)
            print(f"Database: {settings.db_name}")
            conn.close()
            return True
    except Error as e:
        print(f"The error '{e}' occurred")
        return False
