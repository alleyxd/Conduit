"""MCP server: fetch a web page as plain text."""
import html
import re
import urllib.request

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

MAX_CHARS = 15_000

server = MCPServer("web", log_level="CRITICAL")


def to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page)).strip()


@server.tool()
def fetch(url: str) -> str:
    """Download a page over http(s) and return its readable text (first 15,000 characters)."""
    if not url.startswith(("http://", "https://")):
        raise ToolError("only http and https URLs are allowed")
    req = urllib.request.Request(url, headers={"User-Agent": "conduit/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    return to_text(body)[:MAX_CHARS]


if __name__ == "__main__":
    server.run("stdio")
