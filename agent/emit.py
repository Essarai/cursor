"""统一 NDJSON 事件输出（阶段思考过程 + 结果流）。

默认写入 stdout；可通过 set_emit_sink 注入自定义 sink（HTTP 流式响应等）。
"""

from __future__ import annotations

import json
import sys
from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Optional

EmitSink = Callable[[Dict[str, Any]], None]
_sink_var: ContextVar[Optional[EmitSink]] = ContextVar("emit_sink", default=None)


def set_emit_sink(sink: EmitSink) -> Token:
    return _sink_var.set(sink)


def clear_emit_sink(token: Token) -> None:
    _sink_var.reset(token)


def emit(event: str, data: Dict[str, Any] | None = None) -> None:
    payload: Dict[str, Any] = {"event": event}
    if data:
        payload.update(data)

    sink = _sink_var.get()
    if sink is not None:
        sink(payload)
        return

    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)
