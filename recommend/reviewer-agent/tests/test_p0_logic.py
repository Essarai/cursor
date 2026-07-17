from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from agent.chain import ReviewerItem, validate_and_normalize_reviewers
from agent.decision_agent import _select_tool_calls
from agent.scoring import enriched_to_llm_dict
from agent.tools import fetch_author_info_with_memory
from agent.types import EnrichedCandidate


def _candidate(candidate_id: str, name: str, email: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "name": name,
        "org": f"{name}大学",
        "email": email,
        "recent_papers": [{"title": f"{name}的已核实论文"}],
    }


class SubmitValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [
            _candidate("1", "甲", "a@example.com"),
            _candidate("2", "乙", "b@example.com"),
            _candidate("3", "丙", "c@example.com"),
        ]

    def _reviewer(self, candidate_id: str, name: str, email: str) -> ReviewerItem:
        return ReviewerItem(
            candidate_id=candidate_id,
            name=name,
            email=email,
            matched_paper=f"{name}的已核实论文",
            reason="研究方向与待审论文直接相关。",
        )

    def test_normalizes_verified_candidates(self) -> None:
        reviewers = [
            self._reviewer("1", "甲", "a@example.com"),
            self._reviewer("2", "乙", "b@example.com"),
            self._reviewer("3", "丙", "c@example.com"),
        ]

        normalized = validate_and_normalize_reviewers(reviewers, self.candidates)

        self.assertEqual([item.candidate_id for item in normalized], ["1", "2", "3"])

    def test_rejects_candidate_outside_pool(self) -> None:
        reviewers = [
            self._reviewer("1", "甲", "a@example.com"),
            self._reviewer("2", "乙", "b@example.com"),
            self._reviewer("404", "丁", "d@example.com"),
        ]

        with self.assertRaisesRegex(ValueError, "候选人不存在"):
            validate_and_normalize_reviewers(reviewers, self.candidates)

    def test_rejects_duplicate_email_and_unverified_paper(self) -> None:
        duplicate = [
            self._reviewer("1", "甲", "a@example.com"),
            self._reviewer("1", "甲", "a@example.com"),
            self._reviewer("3", "丙", "c@example.com"),
        ]
        with self.assertRaisesRegex(ValueError, "重复"):
            validate_and_normalize_reviewers(duplicate, self.candidates)

        wrong_email = [
            self._reviewer("1", "甲", "wrong@example.com"),
            self._reviewer("2", "乙", "b@example.com"),
            self._reviewer("3", "丙", "c@example.com"),
        ]
        with self.assertRaisesRegex(ValueError, "邮箱"):
            validate_and_normalize_reviewers(wrong_email, self.candidates)

        wrong_paper = [
            self._reviewer("1", "甲", "a@example.com").model_copy(
                update={"matched_paper": "模型编造的论文"}
            ),
            self._reviewer("2", "乙", "b@example.com"),
            self._reviewer("3", "丙", "c@example.com"),
        ]
        with self.assertRaisesRegex(ValueError, "代表作"):
            validate_and_normalize_reviewers(wrong_paper, self.candidates)


class ToolBudgetTests(unittest.TestCase):
    def test_submit_remains_active_after_budget_exhaustion(self) -> None:
        calls = [
            {"name": "get_candidate_detail", "id": "detail"},
            {"name": "submit_reviewers", "id": "submit"},
        ]

        active, skipped = _select_tool_calls(calls, 0, 3)

        self.assertEqual([call["id"] for call in active], ["submit"])
        self.assertEqual([call["id"] for call in skipped], ["detail"])

    def test_submit_is_not_cut_off_by_per_step_limit(self) -> None:
        calls = [
            {"name": "get_candidate_detail", "id": "1"},
            {"name": "get_candidate_detail", "id": "2"},
            {"name": "get_candidate_detail", "id": "3"},
            {"name": "submit_reviewers", "id": "submit"},
        ]

        active, skipped = _select_tool_calls(calls, 3, 3)

        self.assertEqual([call["id"] for call in active], ["submit"])
        self.assertEqual([call["id"] for call in skipped], ["1", "2", "3"])


class StrictIdentityTests(unittest.TestCase):
    def test_candidate_id_is_preserved_in_llm_payload(self) -> None:
        candidate = EnrichedCandidate(
            id="author-123",
            name="甲",
            org="甲大学",
            email="a@example.com",
            hindex=1.0,
            activity_score=0.4,
            pubs_last_2_years=0,
            research_keywords=["控制"],
            recent_papers=[],
        )

        payload = enriched_to_llm_dict(candidate)

        self.assertEqual(payload["candidate_id"], "author-123")

    def test_strict_lookup_never_retries_without_org(self) -> None:
        store = Mock()
        store.author_info_key.return_value = "key"
        store.get.return_value = None
        response = {"success": True, "result": {"total": 0, "data": []}}

        with (
            patch("agent.tools.get_memory_store", return_value=store),
            patch("agent.tools._resolve_api_code", return_value="code"),
            patch("agent.tools.search_articles", return_value=response) as search,
        ):
            result = fetch_author_info_with_memory(
                "同名作者",
                "目标大学",
                "2024-2026",
                api_code="code",
                author_id="123",
                strict_identity=True,
            )

        self.assertTrue(result["identity_verified"])
        search.assert_called_once()
        self.assertEqual(search.call_args.kwargs["org"], "目标大学")
        store.author_info_key.assert_called_once_with(
            "同名作者",
            "目标大学",
            "2024-2026",
            1,
            20,
            author_id="123",
        )

    def test_strict_lookup_rejects_missing_org(self) -> None:
        result = fetch_author_info_with_memory(
            "同名作者",
            "",
            strict_identity=True,
        )

        self.assertFalse(result["success"])
        self.assertFalse(result["identity_verified"])


if __name__ == "__main__":
    unittest.main()
