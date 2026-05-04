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
    
def execute_query(query: str) -> dict:
    """Execute a SQL query and return a results. Returns a dict with columns and rows."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        
        rows = cursor.fetchall()
        
        if rows is not None:
            columns = list(rows[0].keys()) if rows else []
            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows)
            }
            
        #For INSERT?UPDATE - commit and return affected rows
        
        connection.commit()
        return {
            "success": True,
            "row_affected": cursor.rowcount
            
        }
    except Error as e:
        return {
            "success": False,
            "error": str(e),
            "rows": [],
            "row_count": 0
        }
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
def test_connection() -> bool:
    #Quick check - is the database reachable
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
           