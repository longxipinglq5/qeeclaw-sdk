import importlib.util
import os
import sys
import types


class FakeModel:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, texts, **_kwargs):
        vectors = []
        for text in texts:
            seed = sum(ord(ch) for ch in text) or 1
            vectors.append([float((seed + i) % 17) for i in range(768)])
        return vectors


class FakeSearch:
    def __init__(self, rows):
        self.rows = rows
        self._limit = 5
        self._scope = None

    def limit(self, value):
        self._limit = value
        return self

    def where(self, expr, prefilter=True):
        if "scope = '" in expr:
            self._scope = expr.split("scope = '", 1)[1].split("'", 1)[0]
        return self

    def to_list(self):
        rows = self.rows
        if self._scope:
            rows = [r for r in rows if r.get("scope") == self._scope]
        output = []
        for row in rows[: self._limit]:
            output.append({**row, "_distance": 0.05, "_score": 0.95})
        return output


class FakeTable:
    def __init__(self):
        self.rows = []

    def add(self, rows):
        self.rows.extend(rows)

    def delete(self, expr):
        if expr == "id = '_schema'":
            self.rows = [r for r in self.rows if r.get("id") != "_schema"]
            return
        if "doc_id = '" in expr:
            doc_id = expr.split("doc_id = '", 1)[1].split("'", 1)[0]
            self.rows = [r for r in self.rows if r.get("doc_id") != doc_id]

    def search(self, *_args, **_kwargs):
        return FakeSearch(self.rows)


class FakeDb:
    def __init__(self):
        self.tables = {}

    def table_names(self):
        return list(self.tables.keys())

    def create_table(self, name, data, mode="create"):
        table = FakeTable()
        table.add(data)
        self.tables[name] = table
        return table

    def open_table(self, name):
        return self.tables[name]


def load_module(tmp_path, monkeypatch):
    fake_db = FakeDb()
    fake_lancedb = types.SimpleNamespace(connect=lambda _path: fake_db)
    fake_st = types.SimpleNamespace(SentenceTransformer=FakeModel)
    monkeypatch.setitem(sys.modules, "lancedb", fake_lancedb)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("QEECLAW_KB_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("QEECLAW_KB_EMBEDDING_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("QEECLAW_KB_EMBEDDING_DEVICE", "cpu")

    spec = importlib.util.spec_from_file_location(
        "knowledge_store_under_test",
        os.path.join(os.path.dirname(__file__), "knowledge_store.py"),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_lancedb_local_store_ingest_search_delete(tmp_path, monkeypatch):
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
    assert stats["vector_backend"] == "lancedb"
    assert stats["document_count"] == 1
    assert stats["embedding_model"] == "BAAI/bge-base-zh-v1.5"

    deleted = ks.delete_document(result["doc_id"])
    assert deleted["success"] is True
    assert ks.list_documents() == []
