from knowledgeqa.rerank import HttpReranker, NoopReranker


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append((url, headers, json, timeout))
        return FakeResponse(self.payload)


def test_noop_reranker_returns_top_k() -> None:
    hits = [{"id": 1}, {"id": 2}, {"id": 3}]

    assert NoopReranker().rerank("q", hits, top_k=2) == [{"id": 1}, {"id": 2}]


def test_http_reranker_sorts_by_returned_score() -> None:
    client = FakeHttpClient(
        {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.2},
            ]
        }
    )
    reranker = HttpReranker(
        endpoint="https://rerank.example/v1/rerank",
        api_key="secret",
        model="rerank-model",
        client=client,
    )
    hits = [{"text": "first"}, {"text": "second"}]

    result = reranker.rerank("query", hits, top_k=2)

    assert [hit["text"] for hit in result] == ["second", "first"]
    assert result[0]["rerank_score"] == 0.95
    assert client.calls[0][0] == "https://rerank.example/v1/rerank"
    assert client.calls[0][1]["Authorization"] == "Bearer secret"
