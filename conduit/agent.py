import asyncio
import json
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from .pool import ToolPool
from .trace import Tracer

SYSTEM = (
    "You are a careful assistant that answers by using the tools available to you. "
    "Look things up instead of guessing, check results before relying on them, and stop as soon as you can "
    "answer. If a tool returns an error, read it and try a different approach. "
    "Never make up names, numbers or policies: every fact in your answer must come from a tool result. "
    "If you could not find something, say so plainly. "
    "Refer to people and products by name, not by internal ids. "
    "Documents are short: if a keyword search finds nothing, list the files and read the ones that look relevant. "
    "Finish with a short, direct answer."
)


@dataclass
class Result:
    answer: str
    steps: int
    tool_calls: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    stopped: str = "answered"
    events: list = field(default_factory=list, repr=False)


class Agent:
    def __init__(self, pool: ToolPool, base_url: str, model: str, api_key: str = "local",
                 max_steps: int = 12, system: str = SYSTEM, sources: dict | None = None, thinking: bool = False,
                 tracer: Tracer | None = None, on_event=None):
        self.pool = pool
        self.llm = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.max_steps = max_steps
        self.system = system
        if sources:
            self.system += "\n\nSources you can use:\n" + "\n".join(f"- {k}: {v}" for k, v in sources.items())
        # Qwen3-style models think before answering; off by default because it costs most of the latency
        self.extra = {"chat_template_kwargs": {"enable_thinking": thinking}}
        self.tracer = tracer or Tracer(None)
        self.on_event = on_event or (lambda kind, data: None)

    def _emit(self, kind, **data):
        self.tracer.log(kind, **data)
        self.on_event(kind, data)

    async def _run_tool(self, call):
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as e:
            return call, f"arguments were not valid JSON: {e}", False, 0.0
        t = time.time()
        text, ok = await self.pool.call(call.function.name, args)
        return call, text, ok, time.time() - t

    async def run(self, question: str) -> Result:
        t0 = time.time()
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": question}]
        tools = self.pool.openai_tools()
        res = Result(answer="", steps=0, tool_calls=0)
        self._emit("start", question=question, tools=[t["function"]["name"] for t in tools])

        for step in range(1, self.max_steps + 1):
            t = time.time()
            reply = await self.llm.chat.completions.create(model=self.model, messages=messages, tools=tools,
                                                          extra_body=self.extra)
            msg = reply.choices[0].message
            res.steps = step
            if reply.usage:
                res.prompt_tokens += reply.usage.prompt_tokens
                res.completion_tokens += reply.usage.completion_tokens
            self._emit("llm", step=step, seconds=round(time.time() - t, 2),
                       tool_calls=[c.function.name for c in msg.tool_calls or []])

            if not msg.tool_calls:
                res.answer = (msg.content or "").strip()
                break

            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [c.model_dump() for c in msg.tool_calls]})
            # independent calls from the same step run concurrently
            for call, text, ok, secs in await asyncio.gather(*(self._run_tool(c) for c in msg.tool_calls)):
                res.tool_calls += 1
                self._emit("tool", name=call.function.name, args=call.function.arguments, ok=ok,
                           seconds=round(secs, 2), preview=text[:300])
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
        else:
            res.stopped = "max_steps"
            res.answer = "Stopped: reached the step limit before finishing."

        res.seconds = round(time.time() - t0, 2)
        res.events = self.tracer.events
        self._emit("end", answer=res.answer, steps=res.steps, tool_calls=res.tool_calls,
                   seconds=res.seconds, stopped=res.stopped)
        return res
