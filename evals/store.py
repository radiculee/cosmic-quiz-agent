"""Reading and writing eval results as JSON Lines, one record per line, safe across threads."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel

RESULTS_DIR = Path("evals") / "results"
ITEMS_FILE = "items.jsonl"
SEEDED_FILE = "seeded.jsonl"
SEEDED_RESULTS_FILE = "seeded_results.jsonl"


class JsonLinesWriter:
    """Appends models to a .jsonl file; each record is flushed as soon as it is written, so an
    interrupted run keeps everything finished so far."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: BaseModel) -> None:
        line = record.model_dump_json() + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def read_lines[ModelT: BaseModel](path: Path, model: type[ModelT]) -> Iterator[ModelT]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield model.model_validate_json(line)
