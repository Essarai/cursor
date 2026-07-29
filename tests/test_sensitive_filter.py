"""阶段一敏感过滤与回补单测。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent.filters import (
    STAGE1_MAX_SELECTED,
    is_blacklisted_candidate,
    is_sensitive_candidate,
    load_stage1_blacklist,
    select_highest_overlap,
)
from agent.types import ReviewerCandidate


def _cand(
    name: str,
    org: str = "某大学",
    *,
    keywords: list[str] | None = None,
    subject: str = "",
    hindex: float = 10.0,
    email: str | None = None,
    candidate_id: str | None = None,
) -> ReviewerCandidate:
    return ReviewerCandidate(
        id=candidate_id or name,
        name=name,
        org=org,
        email=email or f"{name}@example.com",
        hindex=hindex,
        research_keywords=keywords or ["非局部效应", "时滞", "行波解"],
        subject=subject,
    )


class SensitiveFilterTests(unittest.TestCase):
    def test_military_org_is_sensitive(self):
        c = _cand("郭齐胜", "解放军陆军装甲兵学院", subject="军事装备")
        self.assertTrue(is_sensitive_candidate(c))

    def test_civilian_org_not_sensitive(self):
        c = _cand("张三", "浙江大学", keywords=["偏微分方程"])
        self.assertFalse(is_sensitive_candidate(c))

    def test_select_skips_sensitive_and_backfills(self):
        # 超过上限：前 3 名敏感，需从 Top-N 之外回补
        max_n = STAGE1_MAX_SELECTED
        candidates = [
            _cand("军A", "解放军陆军工程大学", hindex=100),
            _cand("军B", "海军工程大学", hindex=99),
            _cand("军C", "空军工程大学", hindex=98),
            *[
                _cand(f"民{i}", "复旦大学", hindex=90 - i)
                for i in range(max_n + 2)
            ],
        ]
        paper_kw = ["非局部效应", "时滞", "行波解"]
        _, selected, meta = select_highest_overlap(candidates, paper_kw, "")

        selected_names = {c.name for c in selected}
        self.assertNotIn("军A", selected_names)
        self.assertNotIn("军B", selected_names)
        self.assertNotIn("军C", selected_names)
        self.assertEqual(meta["sensitive_filtered_count"], 3)
        self.assertEqual(meta["sensitive_backfilled_count"], 3)
        self.assertEqual(len(selected), max_n)
        self.assertTrue(all(not n.startswith("军") for n in selected_names))

    def test_blacklist_name_is_sensitive_and_backfilled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blacklist.json"
            path.write_text(
                json.dumps(
                    {
                        "names": ["唐功友"],
                        "emails": [],
                        "candidate_ids": [],
                        "name_orgs": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"AGENT_STAGE1_BLACKLIST_PATH": str(path)}
            ):
                load_stage1_blacklist(force=True)
                blocked = _cand("唐功友", "中国海洋大学", hindex=50)
                self.assertTrue(is_blacklisted_candidate(blocked))
                self.assertTrue(is_sensitive_candidate(blocked))

                max_n = STAGE1_MAX_SELECTED
                candidates = [
                    blocked,
                    *[
                        _cand(f"民{i}", "复旦大学", hindex=40 - i)
                        for i in range(max_n + 1)
                    ],
                ]
                _, selected, meta = select_highest_overlap(
                    candidates, ["非局部效应", "时滞", "行波解"], ""
                )
                selected_names = {c.name for c in selected}
                self.assertNotIn("唐功友", selected_names)
                self.assertEqual(meta["sensitive_filtered_count"], 1)
                self.assertEqual(len(selected), max_n)
            load_stage1_blacklist(force=True)


if __name__ == "__main__":
    unittest.main()
