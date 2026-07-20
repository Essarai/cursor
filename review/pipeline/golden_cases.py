"""历史黄金案例注入。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_CASES_PATH = ROOT / "prompts" / "golden_cases.md"


def load_golden_cases(path: Path | None = None) -> str:
    golden_path = path or DEFAULT_GOLDEN_CASES_PATH
    if golden_path.is_file():
        return golden_path.read_text(encoding="utf-8").strip()
    return ""
