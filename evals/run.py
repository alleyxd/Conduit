"""Run the task suite against the agent and write a results table.

python evals/run.py [--think] [--repeat 3]
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.tasks import build, score  # noqa: E402
from conduit.agent import Agent  # noqa: E402
from conduit.cli import load_config  # noqa: E402
from conduit.pool import ToolPool  # noqa: E402


async def main_async(args):
    cfg = load_config(args.config)
    tasks = build()
    rows = []
    async with ToolPool(cfg["servers"], allow=cfg.get("allow")) as pool:
        sources = {k: v["about"] for k, v in cfg["servers"].items() if "about" in v}
        for task in tasks:
            for r in range(args.repeat):
                agent = Agent(pool, cfg["model"]["base_url"], cfg["model"]["name"], cfg["model"]["api_key"],
                              thinking=args.think, sources=sources)
                res = await agent.run(task["q"])
                ok = score(res.answer, task["expect"])
                rows.append({"id": task["id"], "kind": task["kind"], "ok": ok, "steps": res.steps,
                             "tool_calls": res.tool_calls, "seconds": res.seconds,
                             "tokens": res.prompt_tokens + res.completion_tokens, "answer": res.answer[:400]})
                print(f"{task['id']:16} {'PASS' if ok else 'fail'}  {res.seconds:6.1f}s  {res.tool_calls} calls", flush=True)

    mode = "think" if args.think else "fast"
    summary = {"mode": mode, "model": cfg["model"]["name"], "runs": len(rows),
               "success": round(sum(r["ok"] for r in rows) / len(rows), 3),
               "median_seconds": statistics.median(r["seconds"] for r in rows),
               "mean_tool_calls": round(statistics.mean(r["tool_calls"] for r in rows), 2),
               "by_kind": {k: round(statistics.mean(r["ok"] for r in rows if r["kind"] == k), 3)
                           for k in sorted({r["kind"] for r in rows})}}
    out = Path("evals/results")
    out.mkdir(exist_ok=True)
    (out / f"{mode}-{time.strftime('%Y%m%d-%H%M')}.json").write_text(json.dumps({"summary": summary, "runs": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="servers.json")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--repeat", type=int, default=3)
    asyncio.run(main_async(ap.parse_args()))
