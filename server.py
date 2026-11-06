from mcp.server.mcpserver import MCPServer
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "chinook.db"
MAX_ROWS = 200

mcp = MCPServer("db-assistant")

def get_conn() -> sqlite3.Connection:
    # mode=ro makes the connection read-only at the database level
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


@mcp.tool()
def list_tables() -> list[str]:
    """List all the table names in the database."""
    with get_conn() as conn:
        return table_names(conn)


@mcp.tool()
def describe_table(name: str) -> dict:
    """Show a table's columns, foreign keys and 3 sample rows."""

    with get_conn() as conn:
        if name not in table_names(conn):
            raise ValueError(f"Unknown table name: '{name}' . Use the list_tables first.")
        
        columns = [
            {"name": c["name"], "type": c["type"], "primary_key": bool(c["pk"])}
            for c in conn.execute(f'PRAGMA table_info("{name}")') 
        ]

        fkeys = [
            {"column": f["from"], "references": f'{f["table"]}.{f["to"]}'}
            for f in conn.execute(f'PRAGMA foreign_key_list("{name}")')
        ]

        sample = [dict(r) for r in conn.execute(f'SELECT * FROM "{name}" LIMIT 3')]

        return {'columns': columns, 'foreign_keys': fkeys, 'sample_rows': sample}

@mcp.tool()
def run_query(sql: str) -> dict:
    """Run a read-only SQL query (SQLite dialect). Returns at most 200 rows."""
    with get_conn() as conn:
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(MAX_ROWS + 1)
        except sqlite3.Error as e:
            # Returning the error text lets the model fix its own query
            raise ValueError(f"SQL error: {e}")
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {
            'columns': [d[0] for d in cur.description] if cur.description else [],
            'rows': [list(r) for r in rows],
            'row_count': len(rows),
            'truncated': truncated
        }


if __name__ == "__main__":
    mcp.run()