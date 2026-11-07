import logging
import time
import json
import sqlite3
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from contextlib import closing

import sqlglot
from sqlglot import exp


DB_PATH = Path(__file__).parent / "chinook.db"
MAX_ROWS = 200
TIMEOUT_S = 5.0

# Log to a file
logging.basicConfig(
    filename=Path(__file__).parent / "queries.log",
    level = logging.INFO,
    format = "%(asctime)s %(levelname)s %(message)s"
)

mcp = MCPServer("db-assistant")

def get_conn() -> sqlite3.Connection:
    # mode=ro makes the connection read-only at the database level
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # Abort any query that runs longer than TIMEOUT_S
    deadline = time.monotonic() + TIMEOUT_S
    conn.set_progress_handler(
        lambda: 1 if time.monotonic() > deadline else 0, 10_000
    )
    return conn

def validate_select(sql: str) -> None:
    """Allow exactly one SELECT-style statement; reject everything else."""
    try:
        statements = [s for s in sqlglot.parse(sql, read='sqlite') if s is not None]
    except sqlglot.errors.ParseError as e:
        raise ValueError(f'Could not parse SQL: {e}')
    if len(statements) != 1:
        raise ValueError('Only a single SQL statement is allowed.')
    if not isinstance(statements[0], (exp.Select, exp.Union)):
        raise ValueError('Only SELECT queries are allowed')


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


@mcp.tool()
def list_tables() -> list[str]:
    """List all the table names in the database."""
    with closing(get_conn()) as conn:
        return table_names(conn)


@mcp.tool()
def describe_table(name: str) -> dict:
    """Show a table's columns, foreign keys and 3 sample rows."""

    with closing(get_conn()) as conn:
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
    logging.info("QUERY: %s", sql)
    try:
        validate_select(sql)
        with closing(get_conn()) as conn:
            cur = conn.execute(sql)
            rows = cur.fetchmany(MAX_ROWS + 1)
    
    except (sqlite3.Error, sqlite3.Warning, ValueError) as e:
        logging.warning("REJECTED/FAILED: %s", e)
        raise ValueError(f"Query failed: {e}")

    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    return {
    'columns': [d[0] for d in cur.description] if cur.description else [],
    'rows': [list(r) for r in rows],
    'row_count': len(rows),
    'truncated': truncated
    }

@mcp.resource("schema://main")
def schema_resource() -> str:
    """The full database schema as CREATE statements."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    
    return "\n\n".join(r["sql"] + ";" for r in rows)

@mcp.resource("table://{name}")
def table_resource(name: str) -> str:
    """Columns, foreign keys and sample rows from one table."""
    return json.dumps(describe_table(name), indent=2, default=str)



if __name__ == "__main__":
    mcp.run()