"""MCP server: read-only access to one folder."""
import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROOT = Path(os.environ.get("FILES_ROOT", sys.argv[1] if len(sys.argv) > 1 else ".")).resolve()
MAX_BYTES = 20_000

server = MCPServer("files", log_level="CRITICAL")


def inside(rel: str) -> Path:
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ToolError(f"{rel!r} is outside the allowed folder")
    if not p.exists():
        raise ToolError(f"{rel!r} does not exist; paths are relative to the documents root, use '.' for the root")
    return p


@server.tool()
def list_files(folder: str = ".") -> list[str]:
    """List document paths, recursively. `folder` is relative to the documents root; leave it out to list everything."""
    base = inside(folder)
    return sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file())


@server.tool()
def read_file(path: str) -> str:
    """Return the text of a file (first 20,000 bytes)."""
    data = inside(path).read_bytes()[:MAX_BYTES]
    return data.decode("utf-8", errors="replace")


@server.tool()
def search(text: str) -> list[dict]:
    """Search every document for lines containing `text` (case-insensitive). Returns file, line number and line.
    Use one or two key words, e.g. "shipping" or "refund"."""
    hits = []
    needle = text.lower()
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if needle in line.lower():
                hits.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"), "line": i, "text": line.strip()[:300]})
                if len(hits) >= 50:
                    return hits
    return hits


if __name__ == "__main__":
    server.run("stdio")
