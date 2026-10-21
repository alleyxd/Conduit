import argparse
import asyncio
import json
import os
from pathlib import Path

from .agent import Agent
from .pool import ToolPool
from .trace import Tracer


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("model", {})
    cfg["model"].setdefault("base_url", os.environ.get("CONDUIT_BASE_URL", "http://localhost:8000/v1"))
    cfg["model"].setdefault("name", os.environ.get("CONDUIT_MODEL", "local"))
    cfg["model"].setdefault("api_key", os.environ.get("CONDUIT_API_KEY", "local"))
    return cfg


def show(kind, data):
    if kind == "llm" and data["tool_calls"]:
        print(f"  step {data['step']}: model wants {', '.join(data['tool_calls'])} ({data['seconds']}s)")
    elif kind == "tool":
        mark = "ok" if data["ok"] else "error"
        print(f"    {data['name']}({data['args']}) -> {mark}: {data['preview'][:120]!r}")


async def main_async(args):
    cfg = load_config(args.config)
    async with ToolPool(cfg["servers"], allow=cfg.get("allow")) as pool:
        agent = Agent(pool, cfg["model"]["base_url"], cfg["model"]["name"], cfg["model"]["api_key"],
                      max_steps=args.max_steps, thinking=args.think,
                      sources={k: v["about"] for k, v in cfg["servers"].items() if "about" in v},
                      tracer=Tracer(args.trace), on_event=None if args.quiet else show)
        res = await agent.run(args.question)
    print("\n" + res.answer)
    print(f"\n[{res.steps} steps, {res.tool_calls} tool calls, {res.prompt_tokens + res.completion_tokens} tokens, "
          f"{res.seconds}s]")


def main():
    ap = argparse.ArgumentParser(prog="conduit", description="Answer a question with an LLM and MCP tools.")
    ap.add_argument("question")
    ap.add_argument("--config", default="servers.json")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--trace", default="traces")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--think", action="store_true", help="let reasoning models think before each step (slower)")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
