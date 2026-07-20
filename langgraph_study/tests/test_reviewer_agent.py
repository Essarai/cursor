import json
import unittest

from bot.reviewer_agent import ReviewerSelectionAgent, run_reviewer_selection
from bot.reviewer_models import (
    ArticleRelevanceBatch,
    KeywordExtraction,
    ManuscriptInput,
)


class FakeStructuredRunnable:
    def __init__(self, schema, call_log):
        self.schema = schema
        self.call_log = call_log

    def invoke(self, messages):
        self.call_log.append(self.schema.__name__)
        if self.schema is KeywordExtraction:
            return {
                "keywords": ["人工智能", "图神经网络", "药物发现"],
                "reasoning": "覆盖方法、技术和应用领域。",
            }
        payload = json.loads(messages[-1].content)
        return {
            "assessments": [
                {
                    "article_id": article["article_id"],
                    "relevant": True,
                    "reason": "主题相关",
                }
                for article in payload["articles"]
            ]
        }


class FakeLLM:
    def __init__(self):
        self.call_log = []

    def with_structured_output(self, schema, **kwargs):
        self.last_schema = schema
        return FakeStructuredRunnable(schema, self.call_log)


class FakeCscdClient:
    def get_peer_reviewer_candidates(self, keywords, max_results=100):
        return [
            {
                "id": str(index),
                "authorName": f"候选人{index}",
                "org": f"机构{index}",
                "hindex": index + 1,
                "keyword": "人工智能;;图神经网络;;药物发现",
            }
            for index in range(12)
        ]

    def get_author_articles(self, author, org, max_results=100):
        reviewer_id = author.removeprefix("候选人")
        return [
            {
                "cscdId": f"article-{reviewer_id}",
                "title": "图神经网络辅助药物发现",
                "keywords": "人工智能;药物发现",
                "abstract": "使用图神经网络预测药物性质。",
                "citation": "测试期刊,2026",
                "authors": author,
            }
        ]


class ReviewerAgentTests(unittest.TestCase):
    def setUp(self):
        self.llm = FakeLLM()
        self.agent = ReviewerSelectionAgent(
            llm=self.llm,
            client=FakeCscdClient(),
        )
        self.manuscript = ManuscriptInput(
            title="图神经网络辅助药物发现",
            abstract="研究人工智能方法在药物性质预测中的应用。",
            keywords=["图学习", "药物"],
        )

    def test_keyword_interrupt_can_be_modified_then_workflow_finishes(self):
        thread_id, events = self.agent.start(self.manuscript, "keyword-edit")
        initial_events = list(events)

        self.assertIn("__interrupt__", initial_events[-1])
        snapshot = self.agent.graph.get_state(self.agent.config(thread_id))
        self.assertEqual(snapshot.next, ("confirm_keywords",))

        resumed_events = list(
            self.agent.resume_keywords(
                thread_id,
                ["人工智能", "图学习", "药物发现"],
            )
        )
        state = self.agent.graph.get_state(self.agent.config(thread_id)).values

        self.assertEqual(
            state["core_keywords"],
            ["人工智能", "图学习", "药物发现"],
        )
        self.assertIn("generate_report", resumed_events[-1])
        self.assertGreaterEqual(len(state["final_reviewers"]), 3)
        self.assertIn("# 审稿人筛选报告", state["report"])

    def test_synchronous_python_method_auto_approves_keywords(self):
        state = run_reviewer_selection(
            self.manuscript,
            agent=self.agent,
        )

        self.assertEqual(
            state["core_keywords"],
            ["人工智能", "图神经网络", "药物发现"],
        )
        self.assertTrue(state["report"])
        self.assertLessEqual(len(state["final_reviewers"]), 5)

    def test_semantic_check_limited_to_top_candidates(self):
        llm = FakeLLM()
        agent = ReviewerSelectionAgent(
            llm=llm,
            client=FakeCscdClient(),
            semantic_check_top=2,
        )
        state = run_reviewer_selection(self.manuscript, agent=agent)

        relevance_calls = [
            name for name in llm.call_log if name == "ArticleRelevanceBatch"
        ]
        # 10 名初筛候选人中只有词面匹配最多的 2 人做语义复核
        self.assertEqual(len(relevance_calls), 2)
        # 未复核者仍应有词面匹配得出的相关发文数
        self.assertTrue(
            all(
                reviewer["relevant_article_count"] >= 1
                for reviewer in state["final_reviewers"]
            )
        )
        self.assertTrue(
            any("语义复核" in warning for warning in state["warnings"])
        )

    def test_keyword_count_above_four_is_rejected_on_resume(self):
        thread_id, events = self.agent.start(self.manuscript, "too-many-keywords")
        list(events)

        with self.assertRaises(Exception):
            list(
                self.agent.resume_keywords(
                    thread_id,
                    ["一", "二", "三", "四", "五"],
                )
            )


if __name__ == "__main__":
    unittest.main()
