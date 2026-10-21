import json
import time
import uuid
from pathlib import Path


class Tracer:
    """Appends one JSON line per event, so a run can be replayed or analysed later."""

    def __init__(self, folder: str | None):
        self.run_id = uuid.uuid4().hex[:12]
        self.path = None
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.path = Path(folder) / f"{time.strftime('%Y%m%d-%H%M%S')}-{self.run_id}.jsonl"
        self.events = []

    def log(self, kind: str, **data):
        event = {"t": round(time.time(), 3), "run": self.run_id, "kind": kind, **data}
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str, ensure_ascii=False) + "\n")
