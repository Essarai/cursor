"""本地调试用的 runtime stub；部署到平台时由平台注入真实 runtime。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


class Logger:
    def info(self, msg: str) -> None:
        print(f"[INFO] {msg}")

    def error(self, msg: str) -> None:
        print(f"[ERROR] {msg}")


@dataclass
class Args(Generic[T]):
    input: T
    logger: Logger
