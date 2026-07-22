"""关键词重合度精细化计分单测。"""

from __future__ import annotations

import unittest

from agent.filters import (
    aggregate_term_scores,
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
        term_scores = [chaos, 0.7, 0.0]
        expected = aggregate_term_scores(term_scores)
        self.assertAlmostEqual(score, expected, places=6)
        self.assertGreater(chaos, 0.0)

    def test_single_exact_hit_is_not_full_score(self):
        # 两词只精确命中其一：0.6*1 + 0.4*0.5 = 0.8，不再是 1.0
        score = keyword_overlap_score(
            parse_keywords("图像识别,微小弱目标检测"),
            "",
            ["图像识别", "深度学习"],
        )
        self.assertAlmostEqual(score, 0.8, places=6)

    def test_dual_exact_beats_single_exact(self):
        single = keyword_overlap_score(
            parse_keywords("图像识别,微小弱目标检测"),
            "",
            ["图像识别"],
        )
        both = keyword_overlap_score(
            parse_keywords("图像识别,微小弱目标检测"),
            "",
            ["图像识别", "微小弱目标检测"],
        )
        self.assertLess(single, both)
        self.assertAlmostEqual(both, 1.0, places=6)
        self.assertAlmostEqual(single, 0.8, places=6)

    def test_specialist_keyword_still_passes_threshold(self):
        # 三词只精匹配专有词：0.6*1 + 0.4*(1/3) ≈ 0.733，应高于 0.5
        score = keyword_overlap_score(
            parse_keywords("DNA损伤应答,有丝分裂,猪圆环病毒2型"),
            "",
            ["猪圆环病毒2型", "衣壳蛋白"],
        )
        self.assertGreaterEqual(score, 0.5)
        self.assertLess(score, 0.85)

    def test_unrelated_keywords_near_zero(self):
        score = keyword_overlap_score(
            parse_keywords("医学图像分割,半监督学习"),
            "",
            ["材料力学", "疲劳断裂"],
        )
        self.assertLess(score, 0.15)

    def test_aggregate_term_scores_examples(self):
        self.assertAlmostEqual(aggregate_term_scores([1.0, 0.0]), 0.8, places=6)
        self.assertAlmostEqual(aggregate_term_scores([1.0, 1.0]), 1.0, places=6)
        self.assertAlmostEqual(aggregate_term_scores([1.0, 0.7]), 0.94, places=6)
        self.assertAlmostEqual(aggregate_term_scores([1.0, 0.0, 0.0]), 0.733333, places=5)


if __name__ == "__main__":
    unittest.main()
