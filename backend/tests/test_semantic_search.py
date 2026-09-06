from semantic_search import SemanticIndex


class FakeProvider:
    model = "test-embedding-model"
    available = True

    def embed(self, texts):
        return [[1.0, 0.0] if "secure" in text.lower() else [0.0, 1.0] for text in texts]


def test_semantic_index_returns_meaningful_matches(tmp_path):
    index = SemanticIndex(tmp_path / "semantic.json", provider=FakeProvider())
    index.path.write_text(
        '{"documents": ['
        '{"source_type": "telegram", "source_id": "7", "case_id": null, "vector": [1, 0]},'
        '{"source_type": "telegram", "source_id": "8", "case_id": null, "vector": [0, 1]}'
        ']}'
    )

    results = index.search("secure private delivery", {"telegram"}, top_k=1)

    assert len(results) == 1
    assert results[0]["source_id"] == "7"
    assert results[0]["score"] == 1.0


def test_semantic_index_is_safe_without_provider(tmp_path):
    class UnavailableProvider:
        available = False

    index = SemanticIndex(tmp_path / "missing.json", provider=UnavailableProvider())

    assert index.search("anything") == []