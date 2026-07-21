"""Agent 统一运行入口（CLI / HTTP 共用）。"""

from __future__ import annotations

import queue
import threading
from typing import Any, Dict, Iterator

from agent.chain import stream_semantic_screening
from agent.emit import clear_emit_sink, set_emit_sink
from agent.pipeline import run_pipeline
from agent.types import PaperInput


def iter_agent_events(paper: PaperInput) -> Iterator[Dict[str, Any]]:
    """运行完整三阶段管线，逐条 yield NDJSON 事件 dict。"""
    event_queue: queue.SimpleQueue = queue.SimpleQueue()

    def sink(payload: Dict[str, Any]) -> None:
        event_queue.put(payload)

    def worker() -> None:
        token = set_emit_sink(sink)
        try:
            pipeline_result = run_pipeline(paper)
            stream_semantic_screening(pipeline_result["llm_payload"])
        except Exception as exc:
            event_queue.put({"event": "error", "message": str(exc)})
        finally:
            clear_emit_sink(token)
            event_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        yield item

    thread.join()
