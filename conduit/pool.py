import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import Client, StdioServerParameters


@dataclass
class Tool:
    server: str
    name: str
    description: str
    schema: dict
    client: Client = field(repr=False)

    @property
    def qualified(self):
        return f"{self.server}__{self.name}"


class ToolPool:
    """Connects to every configured MCP server and exposes their tools under one namespace."""

    def __init__(self, servers: dict, allow: list[str] | None = None, timeout: float = 60):
        self.servers = servers
        self.allow = set(allow) if allow else None
        self.timeout = timeout
        self.tools: dict[str, Tool] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self):
        for name, spec in self.servers.items():
            cmd = sys.executable if spec["command"] in ("python", "python3") else spec["command"]
            params = StdioServerParameters(command=cmd, args=spec.get("args", []),
                                           env={**os.environ, **spec.get("env", {})})
            client = await self._stack.enter_async_context(Client(params))
            for t in (await client.list_tools()).tools:
                tool = Tool(name, t.name, t.description or "", t.input_schema, client)
                if self.allow is None or tool.qualified in self.allow:
                    self.tools[tool.qualified] = tool
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    def openai_tools(self):
        return [{"type": "function", "function": {"name": t.qualified, "description": t.description,
                                                  "parameters": t.schema}} for t in self.tools.values()]

    async def call(self, qualified: str, args: dict) -> tuple[str, bool]:
        """Returns (text, ok). Errors come back as text so the model can read them and recover."""
        tool = self.tools.get(qualified)
        if tool is None:
            return f"unknown tool {qualified!r}", False
        try:
            res = await asyncio.wait_for(tool.client.call_tool(tool.name, args), self.timeout)
        except TimeoutError:
            return f"{qualified} timed out after {self.timeout:.0f}s", False
        parts = []
        for block in res.content:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else json.dumps(block.model_dump(), default=str))
        return "\n".join(parts) or "(empty result: nothing matched)", not res.is_error
