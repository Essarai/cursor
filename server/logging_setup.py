"""统一应用日志配置，确保 Railway / uvicorn 下 INFO 可见。"""

from __future__ import annotations

import logging

_LOGGER_NAME = "reviewer_agent"
_configured = False


def get_logger(name: str | None = None) -> logging.Logger:
    """返回带 stderr handler 的应用 logger。"""
    global _configured
    root = logging.getLogger(_LOGGER_NAME)
    if not _configured:
        if not root.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
            root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
        _configured = True
    if name:
        return root.getChild(name)
    return root
