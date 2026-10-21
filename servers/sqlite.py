"""MCP server: read-only SQL over one SQLite database."""
import os
import sqlite3
import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DB = os.environ.get("SQLITE_DB", sys.argv[1] if len(sys.argv) > 1 else "data.db")
MAX_ROWS = 200

server = MCPServer("sqlite", log_level="CRITICAL")


def connect():
    # mode=ro: the agent can look but never write
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


@server.tool()
def list_tables() -> list[str]:
    """Names of the tables in the database."""
    with connect() as db:
        return [r[0] for r in db.execute("select name from sqlite_master where type='table' order by name")]


@server.tool()
def describe_table(table: str) -> list[dict]:
    """Columns of a table with their types."""
    with connect() as db:
        if table not in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
            raise ToolError(f"no table named {table!r}")
        return [{"column": r[1], "type": r[2]} for r in db.execute(f'pragma table_info("{table}")')]


@server.tool()
def query(sql: str) -> dict:
    """Run one read-only SELECT statement and return up to 200 rows."""
    if not sql.lstrip().lower().startswith(("select", "with")):
        raise ToolError("only SELECT queries are allowed")
    try:
        with connect() as db:
            cur = db.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as e:
        # pass the database's own message back so the model can fix its query
        raise ToolError(f"SQL error: {e}") from e
    return {"columns": cols, "rows": [list(r) for r in rows[:MAX_ROWS]], "truncated": len(rows) > MAX_ROWS}


if __name__ == "__main__":
    server.run("stdio")
