"""Agent 统一运行入口（CLI / HTTP 共用）。"""

from __future__ import annotations

import queue
import threading
from typing import Any, Dict, Iterator

from agent.chain import stream_semantic_screening
from agent.emit import clear_emit_sink, emit, set_emit_sink
from agent.pipeline import build_llm_payload, run_stage1, run_stage2
from agent.types import PaperInput


def iter_agent_events(paper: PaperInput) -> Iterator[Dict[str, Any]]:
    """运行完整三阶段管线，逐条 yield NDJSON 事件 dict。

    候选专家（阶段一）与 AI 精荐（阶段二/三）隔离：
    阶段一成功后即视为可用；后续敏感内容审核失败等不影响已发出的候选结果。
    """
    event_queue: queue.SimpleQueue = queue.SimpleQueue()

    def sink(payload: Dict[str, Any]) -> None:
        event_queue.put(payload)

    def worker() -> None:
        token = set_emit_sink(sink)
        try:
            session_code = None
            stage1 = run_stage1(paper, session_code)
            emit(
                "stage1_done",
                {
                    "selected_count": len(stage1.get("selected") or []),
                    "total_from_api": stage1.get("total_from_api", 0),
                },
            )

            try:
                enriched = run_stage2(stage1["selected"], session_code)
                payload = build_llm_payload(paper, enriched, stage1)
                stream_semantic_screening(payload)
            except Exception as exc:
                # AI 精荐失败：仅标记 ai 阶段，前端不得覆盖候选专家列表
                event_queue.put(
                    {
                        "event": "error",
                        "stage": "ai",
                        "message": str(exc),
                    }
                )
        except Exception as exc:
            event_queue.put(
                {
                    "event": "error",
                    "stage": "stage1",
                    "message": str(exc),
                }
            )
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
