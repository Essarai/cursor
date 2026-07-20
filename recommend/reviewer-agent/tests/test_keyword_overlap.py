"""关键词重合度精细化计分单测。"""

from __future__ import annotations

import unittest

from agent.filters import (
    keyword_overlap_score,
    parse_keywords,
    token_pair_score,
)


class KeywordOverlapTests(unittest.TestCase):
    def test_exact_match_is_one(self):
        score = keyword_overlap_score(
            parse_keywords("滑模控制,混沌同步"),
            "",
            ["滑模控制", "混沌同步"],
        )
        self.assertEqual(score, 1.0)

    def test_short_token_cannot_substring_alone(self):
        # 「同步」(2/5=0.4 < 0.5) 不得子串命中「自适应同步」
        self.assertEqual(token_pair_score("自适应同步", "同步"), 0.0)
        # 「自适应」(3/5=0.6) 可以子串命中
        self.assertEqual(token_pair_score("自适应同步", "自适应"), 0.7)
        # 「滑模」可命中「滑模控制」(2/4=0.5)
        self.assertEqual(token_pair_score("滑模控制", "滑模"), 0.7)

    def test_chaos_near_match_gets_bigram_credit(self):
        pair = token_pair_score("混沌系统", "混沌同步")
        self.assertGreaterEqual(pair, 0.3)
        self.assertLessEqual(pair, 0.65)

    def test_user_example_finer_scoring(self):
        paper = parse_keywords("混沌系统,自适应同步,分岔分析")
        reviewer = ["混沌同步", "滑模", "分数阶", "自适应", "同步"]
        score = keyword_overlap_score(paper, "", reviewer)
        chaos = token_pair_score("混沌系统", "混沌同步")
        expected = (chaos + 0.7 + 0.0) / 3
        self.assertAlmostEqual(score, expected, places=6)
        self.assertGreater(chaos, 0.0)

    def test_unrelated_keywords_near_zero(self):
        score = keyword_overlap_score(
            parse_keywords("医学图像分割,半监督学习"),
            "",
            ["材料力学", "疲劳断裂"],
        )
        self.assertLess(score, 0.15)


if __name__ == "__main__":
    unittest.main()
