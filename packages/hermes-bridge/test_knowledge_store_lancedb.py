import importlib.util
import os
import sys
import types


class FakeCollection:
    def __init__(self):
        self.rows = []

    def add(self, ids, embeddings, documents, metadatas):
        for item_id, embedding, document, metadata in zip(ids, embeddings, documents, metadatas):
            self.rows.append({
                "id": item_id,
                "embedding": embedding,
                "document": document,
                "metadata": metadata,
            })

    def delete(self, where):
        doc_id = where.get("doc_id")
        self.rows = [row for row in self.rows if row["metadata"].get("doc_id") != doc_id]

    def query(self, query_embeddings, n_results, include, where=None):
        del query_embeddings, include
        rows = self.rows
        if where and where.get("scope"):
            rows = [row for row in rows if row["metadata"].get("scope") == where["scope"]]
        rows = rows[:n_results]
        return {
            "ids": [[row["id"] for row in rows]],
            "documents": [[row["document"] for row in rows]],
            "metadatas": [[row["metadata"] for row in rows]],
            "distances": [[0.05 for _row in rows]],
        }


class FakeClient:
    def __init__(self, path):
        self.path = path
        self.collections = {}

    def get_collection(self, name):
        if name not in self.collections:
            raise ValueError("missing collection")
        return self.collections[name]

    def create_collection(self, name, metadata=None):
        del metadata
        collection = FakeCollection()
        self.collections[name] = collection
        return collection


class FakeEmbedder:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, texts, **_kwargs):
        vectors = []
        for text in texts:
            seed = sum(ord(ch) for ch in text) or 1
            vectors.append([float((seed + i) % 17) for i in range(768)])
        return vectors


def load_module(tmp_path, monkeypatch):
    fake_client = FakeClient
    fake_chromadb = types.SimpleNamespace(PersistentClient=fake_client)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    model_file = tmp_path / "Qwen3-Embedding-0.6B-Q4_0.gguf"
    model_file.write_bytes(b"GGUF" + b"\0" * 16)

    monkeypatch.setenv("QEECLAW_KB_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("QEECLAW_KB_VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("QEECLAW_KB_EMBEDDING_MODEL_FILE", str(model_file))
    monkeypatch.setenv("QEECLAW_KB_EMBEDDING_API_URL", "http://127.0.0.1:8080/embedding")

    spec = importlib.util.spec_from_file_location(
        "knowledge_store_under_test",
        os.path.join(os.path.dirname(__file__), "knowledge_store.py"),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_LlamaServerEmbedder", FakeEmbedder)
    monkeypatch.setattr(module, "_check_embedding_api_health", lambda: None)
    return module


def test_chromadb_local_store_ingest_search_delete(tmp_path, monkeypatch):
    ks = load_module(tmp_path, monkeypatch)

    assert ks.init_knowledge_store() is None
    result = ks.add_document(
        content="企业微信客户跟进规则\n\n重要客户需要在 24 小时内响应。",
        filename="rules.md",
        scope="sales",
    )
    assert result["success"] is True
    assert result["chunk_count"] >= 1

    hits = ks.search_knowledge("客户响应", top_k=3, scope="sales")
    assert len(hits) >= 1
    assert hits[0]["filename"] == "rules.md"
    assert hits[0]["score"] > 0

    stats = ks.get_kb_stats()
    assert stats["vector_backend"] == "chromadb"
    assert stats["document_count"] == 1
    assert stats["embedding_model"] == "Qwen3-Embedding-0.6B-Q4_0"
    assert stats["embedding_model_file_exists"] is True

    deleted = ks.delete_document(result["doc_id"])
    assert deleted["success"] is True
    assert ks.list_documents() == []
