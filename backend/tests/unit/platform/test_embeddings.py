from __future__ import annotations
import commerce_connector.platform.groq as groq_module
from commerce_connector.platform.groq import GroqClient
def test_ollama_embedding_uses_retrieval_prompts_and_768_dimensions(monkeypatch):
    calls: list[dict] = []
    class FakeResponse:
        status_code = 200
        text = ""
        def json(self):
            return {"embeddings": [[0.1] * 768]}
    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()
    monkeypatch.setattr(groq_module.httpx, "post", fake_post)
    client = GroqClient(
        "unused",
        embedding_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_embedding_model="embeddinggemma:latest",
        embedding_dimensions=768,
    )
    query = client.embed("total revenue", task="query")
    document = client.embed("net sales metric", task="document", title="Metric: Revenue")
    assert len(query) == 768
    assert len(document) == 768
    assert calls[0]["url"] == "http://localhost:11434/api/embed"
    assert calls[0]["json"]["model"] == "embeddinggemma:latest"
    assert calls[0]["json"]["input"].startswith("task: search result | query: ")
    assert calls[1]["json"]["input"] == "title: Metric: Revenue | text: net sales metric"
