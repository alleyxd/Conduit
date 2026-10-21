import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.tasks import score  # noqa: E402
from conduit.agent import Agent  # noqa: E402
from conduit.pool import ToolPool  # noqa: E402

SERVERS = {
    "files": {"command": "python", "args": [str(ROOT / "servers/files.py"), str(ROOT / "examples/docs")]},
    "shop": {"command": "python", "args": [str(ROOT / "servers/sqlite.py"), str(ROOT / "examples/shop.db")]},
}


def run(coro):
    return asyncio.run(coro)


def test_pool_lists_namespaced_tools():
    async def go():
        async with ToolPool(SERVERS) as pool:
            names = {t["function"]["name"] for t in pool.openai_tools()}
            assert {"files__search", "files__read_file", "shop__query", "shop__list_tables"} <= names
    run(go())


def test_files_server_stays_inside_root():
    async def go():
        async with ToolPool(SERVERS) as pool:
            text, ok = await pool.call("files__read_file", {"path": "../../servers.json"})
            assert not ok and "outside" in text
    run(go())


def test_sqlite_server_is_read_only_and_explains_errors():
    async def go():
        async with ToolPool(SERVERS) as pool:
            text, ok = await pool.call("shop__query", {"sql": "delete from orders"})
            assert not ok and "only SELECT" in text
            text, ok = await pool.call("shop__query", {"sql": "select nope from orders"})
            assert not ok and "no such column" in text
            text, ok = await pool.call("shop__query", {"sql": "select count(*) n from products"})
            assert ok and json.loads(text)["rows"] == [[10]]
    run(go())


def test_allow_list_hides_other_tools():
    async def go():
        async with ToolPool(SERVERS, allow=["files__search"]) as pool:
            assert [t["function"]["name"] for t in pool.openai_tools()] == ["files__search"]
            text, ok = await pool.call("shop__query", {"sql": "select 1"})
            assert not ok and "unknown tool" in text
    run(go())


class FakeLLM:
    """Plays back scripted replies in place of a model server."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kw):
        self.seen.append(kw["messages"])
        msg = self.replies.pop(0)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def tool_call(name, args, id="c1"):
    fn = SimpleNamespace(name=name, arguments=json.dumps(args))
    call = SimpleNamespace(id=id, function=fn, type="function")
    call.model_dump = lambda: {"id": id, "type": "function", "function": {"name": name, "arguments": fn.arguments}}
    return call


def test_agent_loop_calls_tool_then_answers():
    async def go():
        async with ToolPool(SERVERS) as pool:
            agent = Agent(pool, "http://unused", "fake")
            agent.llm = FakeLLM([
                SimpleNamespace(content="", tool_calls=[tool_call("shop__query", {"sql": "select count(*) from products"})]),
                SimpleNamespace(content="There are 10 products.", tool_calls=None),
            ])
            res = await agent.run("How many products?")
            assert res.answer == "There are 10 products." and res.tool_calls == 1 and res.steps == 2
            tool_msg = agent.llm.seen[1][-1]
            assert tool_msg["role"] == "tool" and "10" in tool_msg["content"]
    run(go())


def test_agent_stops_at_step_limit():
    async def go():
        async with ToolPool(SERVERS) as pool:
            agent = Agent(pool, "http://unused", "fake", max_steps=2)
            agent.llm = FakeLLM([SimpleNamespace(content="", tool_calls=[tool_call("shop__list_tables", {})])] * 2)
            res = await agent.run("loop forever")
            assert res.stopped == "max_steps"
    run(go())


@pytest.mark.parametrize("answer,expect,ok", [
    ("Customer Yusuf Patel spent $1,004.00", ["Yusuf", "1,004"], True),
    ("customer 27 spent 1004", ["Yusuf", "1,004"], False),
    ("Yes, Mateo reached Gold.", ["Mateo", ["yes", "reached"]], True),
])
def test_scorer(answer, expect, ok):
    assert score(answer, expect) is ok
