import unittest
from unittest.mock import Mock, patch

from bot.cscd_client import CscdClient


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class CscdClientTests(unittest.TestCase):
    def test_api_code_reused_then_refreshed_after_idle_timeout(self):
        client = CscdClient()
        client._session = Mock()
        client._session.get.side_effect = [
            FakeResponse({"data": "code-1"}),
            FakeResponse({"result": []}),
            FakeResponse({"result": []}),
            FakeResponse({"data": "code-2"}),
            FakeResponse({"result": []}),
        ]

        with patch(
            "bot.cscd_client.time.monotonic",
            side_effect=[0, 1, 100, 101, 702, 703, 704],
        ):
            client.get_peer_reviewers("关键词一")
            client.search_articles("作者", "机构")
            client.get_peer_reviewers("关键词二")

        calls = client._session.get.call_args_list
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[1].kwargs["headers"]["ApiCode"], "code-1")
        self.assertEqual(calls[2].kwargs["headers"]["ApiCode"], "code-1")
        self.assertEqual(calls[4].kwargs["headers"]["ApiCode"], "code-2")

    def test_candidate_normalization_and_limit(self):
        client = CscdClient()
        client.get_peer_reviewers = Mock(
            return_value={
                "result": [
                    {
                        "id": str(index),
                        "authorName": f"候选人{index}",
                        "hindex": "null" if index == 0 else str(index),
                    }
                    for index in range(120)
                ]
            }
        )

        candidates = client.get_peer_reviewer_candidates("关键词", max_results=100)

        self.assertEqual(len(candidates), 100)
        self.assertIsNone(candidates[0]["hindex"])
        self.assertEqual(candidates[1]["hindex"], "1")

    def test_article_pagination_stops_at_one_hundred(self):
        client = CscdClient()
        pages = []
        for page in range(1, 4):
            pages.append(
                {
                    "result": {
                        "total": 140,
                        "page": page,
                        "limit": 50,
                        "data": [
                            {
                                "cscdId": f"{page}-{index}",
                                "title": f"论文 {page}-{index}",
                            }
                            for index in range(50 if page < 3 else 40)
                        ],
                    }
                }
            )
        client.search_articles = Mock(side_effect=pages)

        articles = client.get_author_articles("作者", "机构", max_results=100)

        self.assertEqual(len(articles), 100)
        self.assertEqual(client.search_articles.call_count, 2)
        client.search_articles.assert_any_call("作者", "机构", page=2, limit=50)


if __name__ == "__main__":
    unittest.main()
