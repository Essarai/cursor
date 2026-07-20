import unittest

from bot.reviewer_scoring import (
    is_recent_article,
    minmax_scores,
    stage1_filter,
    stage2_filter,
)


class ReviewerScoringTests(unittest.TestCase):
    def test_minmax_scores(self):
        self.assertEqual(minmax_scores([10, 20, 30]), [0, 50, 100])
        self.assertEqual(minmax_scores([0, 0]), [0, 0])
        self.assertEqual(minmax_scores([5, 5]), [100, 100])

    def test_stage1_keeps_missing_hindex_and_excludes_same_organization(self):
        candidates = [
            {
                "id": "missing",
                "authorName": "缺失",
                "org": "其他机构",
                "hindex": None,
                "keyword": "图神经网络;;药物发现;;人工智能",
            },
            {
                "id": "conflict",
                "authorName": "同机构",
                "org": "测试大学",
                "hindex": 20,
                "keyword": "图神经网络",
            },
        ]
        candidates.extend(
            {
                "id": str(index),
                "authorName": f"候选人{index}",
                "org": f"机构{index}",
                "hindex": index + 1,
                "keyword": "图神经网络;;药物发现" if index < 6 else "无关领域",
            }
            for index in range(12)
        )

        selected, rejected = stage1_filter(
            candidates,
            ["图神经网络", "药物发现", "人工智能"],
            ["测试大学"],
            keep_count=10,
        )

        self.assertEqual(len(selected), 10)
        selected_ids = {item["id"] for item in selected}
        # H-index 缺失但关键词全中者按关键词分（100% 权重）排在最前
        self.assertIn("missing", selected_ids)
        missing = next(item for item in selected if item["id"] == "missing")
        self.assertIsNone(missing["hindex_score"])
        self.assertEqual(missing["stage1_score"], missing["keyword_score"])
        reasons = {item.get("rejection_reason") for item in rejected}
        self.assertIn("与稿件作者同机构", reasons)
        self.assertNotIn("H-index 缺失", reasons)

    def test_stage1_keeps_top_n_by_relative_score(self):
        candidates = [
            {
                "id": str(index),
                "authorName": f"候选人{index}",
                "org": f"机构{index}",
                "hindex": index + 1,
                "keyword": "图神经网络" if index % 2 == 0 else "其他方向",
            }
            for index in range(15)
        ]

        selected, rejected = stage1_filter(
            candidates,
            ["图神经网络"],
            [],
            keep_count=4,
        )

        self.assertEqual(len(selected), 4)
        self.assertEqual([item["stage1_rank"] for item in selected], [1, 2, 3, 4])
        self.assertEqual(len(rejected), 11)

    def test_recent_year_uses_current_and_previous_two_years(self):
        self.assertTrue(is_recent_article({"citation": "期刊,2026"}, 2026))
        self.assertTrue(is_recent_article({"citation": "期刊,2024"}, 2026))
        self.assertFalse(is_recent_article({"citation": "期刊,2023"}, 2026))

    def test_stage2_excludes_coauthor_and_keeps_top_n(self):
        candidates = [
            {
                "id": str(index),
                "authorName": f"审稿人{index}",
                "org": f"机构{index}",
            }
            for index in range(5)
        ]
        articles = {
            str(index): [
                {
                    "cscdId": f"a{index}",
                    "title": "相关论文",
                    "citation": "期刊,2026",
                    "authors": "稿件作者;审稿人0" if index == 0 else f"审稿人{index}",
                }
            ]
            for index in range(5)
        }
        relevant = {str(index): {f"a{index}"} for index in range(5)}

        selected, rejected = stage2_filter(
            candidates,
            articles,
            relevant,
            ["稿件作者"],
            keep_count=3,
            current_year=2026,
        )

        self.assertEqual(len(selected), 3)
        self.assertNotIn("0", {item["id"] for item in selected})
        self.assertEqual([item["final_rank"] for item in selected], [1, 2, 3])
        self.assertIn(
            "近三年存在共同作者利益冲突",
            {item.get("rejection_reason") for item in rejected},
        )


if __name__ == "__main__":
    unittest.main()
