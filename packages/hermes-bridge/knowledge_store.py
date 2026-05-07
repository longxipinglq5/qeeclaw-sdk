"""
QeeClaw Knowledge Store — local LanceDB + local embedding model.

This module is intentionally offline-only: it never calls cloud embedding APIs
and it refuses to download models at runtime. Package bge-base-zh-v1.5 with the
runtime and point QEECLAW_KB_EMBEDDING_MODEL_DIR at that local directory.

Data storage path: ~/.qeeclaw/knowledge/ by default. Override with QEECLAW_KB_DIR.
"""

import hashlib
import json
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


_lancedb = None
_embedding_model = None
_embedding_backend = ""
_db = None
_table = None
_kb_ready = False
_kb_error: Optional[str] = None
_MODULE_DIR = os.path.abspath(os.path.dirname(__file__))
_CONFIG_DIR = _MODULE_DIR

KB_DIR = os.environ.get(
    "QEECLAW_KB_DIR",
    str(Path.home() / ".qeeclaw" / "knowledge"),
)
KB_VECTOR_BACKEND = os.environ.get("QEECLAW_KB_VECTOR_BACKEND", "lancedb").lower()
KB_TABLE_NAME = os.environ.get("QEECLAW_KB_TABLE", "qeeclaw_knowledge")
KB_EMBEDDING_MODEL = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")
KB_EMBEDDING_MODEL_DIR = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL_DIR", "")
KB_EMBEDDING_ENGINE = os.environ.get("QEECLAW_KB_EMBEDDING_ENGINE", "auto").lower()
KB_DEVICE = os.environ.get("QEECLAW_KB_EMBEDDING_DEVICE", "cpu")
KB_BATCH_SIZE = int(os.environ.get("QEECLAW_KB_EMBEDDING_BATCH_SIZE", "16"))
KB_TOP_K = int(os.environ.get("QEECLAW_KB_TOP_K", "5"))
CHUNK_SIZE = int(os.environ.get("QEECLAW_KB_CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.environ.get("QEECLAW_KB_CHUNK_OVERLAP", "64"))
EMBEDDING_DIMENSION = int(os.environ.get("QEECLAW_KB_EMBEDDING_DIMENSION", "768"))
MIN_SCORE_DEFAULT = float(os.environ.get("QEECLAW_KB_MIN_SCORE", "0.3"))


def _resolve_path(value: str, base_dir: str) -> str:
    if not value:
        return value
    expanded = os.path.expanduser(value)
    if os.path.isabs(expanded):
        return expanded
    return os.path.abspath(os.path.join(base_dir, expanded))

try:
    import yaml as _yaml
    _kb_config_path = os.environ.get(
        "QEECLAW_CONFIG_FILE",
        os.path.join(_MODULE_DIR, "config.yaml"),
    )
    _kb_config_path = os.path.abspath(_kb_config_path)
    if os.path.isfile(_kb_config_path):
        _CONFIG_DIR = os.path.dirname(_kb_config_path)
        with open(_kb_config_path, "r", encoding="utf-8") as _f:
            _kb_cfg = (_yaml.safe_load(_f) or {}).get("knowledge", {})
        if _kb_cfg:
            KB_DIR = _resolve_path(str(_kb_cfg.get("storage_dir") or KB_DIR), _CONFIG_DIR)
            KB_VECTOR_BACKEND = str(_kb_cfg.get("vector_backend") or KB_VECTOR_BACKEND).lower()
            KB_TABLE_NAME = str(_kb_cfg.get("table_name") or KB_TABLE_NAME)
            KB_EMBEDDING_MODEL = str(_kb_cfg.get("embedding_model") or KB_EMBEDDING_MODEL)
            KB_EMBEDDING_MODEL_DIR = _resolve_path(
                str(_kb_cfg.get("embedding_model_dir") or KB_EMBEDDING_MODEL_DIR),
                _CONFIG_DIR,
            )
            KB_EMBEDDING_ENGINE = str(_kb_cfg.get("embedding_engine") or KB_EMBEDDING_ENGINE).lower()
            KB_DEVICE = str(_kb_cfg.get("embedding_device") or KB_DEVICE)
            KB_BATCH_SIZE = int(_kb_cfg.get("embedding_batch_size") or KB_BATCH_SIZE)
            KB_TOP_K = int(_kb_cfg.get("top_k") or KB_TOP_K)
            CHUNK_SIZE = int(_kb_cfg.get("chunk_size") or CHUNK_SIZE)
            CHUNK_OVERLAP = int(_kb_cfg.get("chunk_overlap") or CHUNK_OVERLAP)
            EMBEDDING_DIMENSION = int(_kb_cfg.get("embedding_dimension") or EMBEDDING_DIMENSION)
            MIN_SCORE_DEFAULT = float(_kb_cfg.get("min_score") or MIN_SCORE_DEFAULT)
except Exception:
    pass

# Environment variables are the final override layer. Config files provide
# deployable defaults, while HubOS/run.sh can still pin paths at launch time.
if "QEECLAW_KB_DIR" in os.environ:
    KB_DIR = _resolve_path(os.environ["QEECLAW_KB_DIR"], _CONFIG_DIR)
if "QEECLAW_KB_VECTOR_BACKEND" in os.environ:
    KB_VECTOR_BACKEND = os.environ["QEECLAW_KB_VECTOR_BACKEND"].lower()
if "QEECLAW_KB_TABLE" in os.environ:
    KB_TABLE_NAME = os.environ["QEECLAW_KB_TABLE"]
if "QEECLAW_KB_EMBEDDING_MODEL" in os.environ:
    KB_EMBEDDING_MODEL = os.environ["QEECLAW_KB_EMBEDDING_MODEL"]
if "QEECLAW_KB_EMBEDDING_MODEL_DIR" in os.environ:
    KB_EMBEDDING_MODEL_DIR = _resolve_path(os.environ["QEECLAW_KB_EMBEDDING_MODEL_DIR"], _CONFIG_DIR)
if "QEECLAW_KB_EMBEDDING_ENGINE" in os.environ:
    KB_EMBEDDING_ENGINE = os.environ["QEECLAW_KB_EMBEDDING_ENGINE"].lower()
if "QEECLAW_KB_EMBEDDING_DEVICE" in os.environ:
    KB_DEVICE = os.environ["QEECLAW_KB_EMBEDDING_DEVICE"]
if "QEECLAW_KB_EMBEDDING_BATCH_SIZE" in os.environ:
    KB_BATCH_SIZE = int(os.environ["QEECLAW_KB_EMBEDDING_BATCH_SIZE"])
if "QEECLAW_KB_TOP_K" in os.environ:
    KB_TOP_K = int(os.environ["QEECLAW_KB_TOP_K"])
if "QEECLAW_KB_CHUNK_SIZE" in os.environ:
    CHUNK_SIZE = int(os.environ["QEECLAW_KB_CHUNK_SIZE"])
if "QEECLAW_KB_CHUNK_OVERLAP" in os.environ:
    CHUNK_OVERLAP = int(os.environ["QEECLAW_KB_CHUNK_OVERLAP"])
if "QEECLAW_KB_EMBEDDING_DIMENSION" in os.environ:
    EMBEDDING_DIMENSION = int(os.environ["QEECLAW_KB_EMBEDDING_DIMENSION"])
if "QEECLAW_KB_MIN_SCORE" in os.environ:
    MIN_SCORE_DEFAULT = float(os.environ["QEECLAW_KB_MIN_SCORE"])

_META_FILE = "documents_meta.json"


def _ensure_kb_dir():
    os.makedirs(KB_DIR, exist_ok=True)


def _load_meta() -> Dict[str, Any]:
    meta_path = os.path.join(KB_DIR, _META_FILE)
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"documents": {}}


def _save_meta(meta: Dict[str, Any]):
    _ensure_kb_dir()
    meta_path = os.path.join(KB_DIR, _META_FILE)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _lance_dir() -> str:
    return os.path.join(KB_DIR, "lancedb")


def _resolve_local_model_dir() -> str:
    candidates = []
    if KB_EMBEDDING_MODEL_DIR:
        candidates.append(KB_EMBEDDING_MODEL_DIR)
    candidates.extend([
        os.path.join(KB_DIR, "models", "bge-base-zh-v1.5"),
        os.path.join(_CONFIG_DIR, "models", "bge-base-zh-v1.5"),
        os.path.join(_MODULE_DIR, "models", "bge-base-zh-v1.5"),
        os.path.join(_MODULE_DIR, "vendor", "models", "bge-base-zh-v1.5"),
    ])

    for candidate in candidates:
        expanded = os.path.abspath(os.path.expanduser(candidate))
        if os.path.isdir(expanded) and os.path.isfile(os.path.join(expanded, "config.json")):
            return expanded

    searched = ", ".join(os.path.abspath(os.path.expanduser(p)) for p in candidates)
    raise RuntimeError(
        "Local embedding model not found. Package bge-base-zh-v1.5 locally and set "
        f"QEECLAW_KB_EMBEDDING_MODEL_DIR. Searched: {searched}"
    )


def _find_onnx_model_file(model_dir: str) -> str:
    candidates = [
        os.path.join(model_dir, "onnx", "model_quantized.onnx"),
        os.path.join(model_dir, "onnx", "model.onnx"),
        os.path.join(model_dir, "model_quantized.onnx"),
        os.path.join(model_dir, "model.onnx"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


def _has_sentence_transformer_files(model_dir: str) -> bool:
    return (
        os.path.isfile(os.path.join(model_dir, "modules.json"))
        or os.path.isfile(os.path.join(model_dir, "pytorch_model.bin"))
        or os.path.isfile(os.path.join(model_dir, "model.safetensors"))
    )


class _OnnxBgeEmbedder:
    def __init__(self, model_dir: str):
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Local ONNX embedding dependencies not installed. Build qeeclaw-server runtime "
                "with onnxruntime, tokenizers, and numpy."
            ) from exc

        onnx_model = _find_onnx_model_file(model_dir)
        if not onnx_model:
            raise RuntimeError(f"ONNX embedding model file not found under: {model_dir}")
        tokenizer_file = os.path.join(model_dir, "tokenizer.json")
        if not os.path.isfile(tokenizer_file):
            raise RuntimeError(f"tokenizer.json not found under: {model_dir}")

        providers = ["CPUExecutionProvider"]
        if KB_DEVICE == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        self._np = np
        self._session = ort.InferenceSession(onnx_model, providers=providers)
        self._input_names = {inp.name for inp in self._session.get_inputs()}
        self._tokenizer = Tokenizer.from_file(tokenizer_file)
        self._max_length = int(os.environ.get("QEECLAW_KB_EMBEDDING_MAX_LENGTH", "512"))

    def encode(
        self,
        texts: List[str],
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ):
        del show_progress_bar
        all_vectors = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            encoded = self._tokenizer.encode_batch(batch)
            max_len = min(self._max_length, max((len(item.ids) for item in encoded), default=0))
            if max_len <= 0:
                max_len = 1

            input_ids = []
            attention_mask = []
            token_type_ids = []
            for item in encoded:
                ids = item.ids[:max_len]
                mask = item.attention_mask[:max_len]
                types = item.type_ids[:max_len] if item.type_ids else [0] * len(ids)
                pad_len = max_len - len(ids)
                input_ids.append(ids + [0] * pad_len)
                attention_mask.append(mask + [0] * pad_len)
                token_type_ids.append(types + [0] * pad_len)

            np = self._np
            feeds = {}
            if "input_ids" in self._input_names:
                feeds["input_ids"] = np.asarray(input_ids, dtype=np.int64)
            if "attention_mask" in self._input_names:
                feeds["attention_mask"] = np.asarray(attention_mask, dtype=np.int64)
            if "token_type_ids" in self._input_names:
                feeds["token_type_ids"] = np.asarray(token_type_ids, dtype=np.int64)

            outputs = self._session.run(None, feeds)
            vectors = outputs[0]
            if len(vectors.shape) == 3:
                vectors = vectors[:, 0, :]
            if normalize_embeddings:
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                vectors = vectors / norms
            all_vectors.extend(vectors.astype("float32").tolist())
        return all_vectors


def _load_embedding_model():
    global _embedding_backend, _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    model_dir = _resolve_local_model_dir()
    engine = KB_EMBEDDING_ENGINE
    if engine == "auto":
        engine = "onnx" if _find_onnx_model_file(model_dir) else "sentence-transformers"

    if engine == "onnx":
        _embedding_model = _OnnxBgeEmbedder(model_dir)
        _embedding_backend = "onnx"
        return _embedding_model

    if engine in ("sentence-transformers", "sentence_transformers", "st"):
        if not _has_sentence_transformer_files(model_dir):
            raise RuntimeError(
                "Local sentence-transformers model files not found. Use a full local "
                "sentence-transformers model directory, or package the ONNX model under "
                "models/bge-base-zh-v1.5/onnx/model_quantized.onnx."
            )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers package not installed. Build qeeclaw-server runtime "
                "with sentence-transformers, or use the packaged ONNX bge-base-zh-v1.5 model."
            ) from exc
        _embedding_model = SentenceTransformer(
            model_dir,
            device=KB_DEVICE,
            local_files_only=True,
        )
        _embedding_backend = "sentence-transformers"
        return _embedding_model

    raise RuntimeError(f"Unsupported local embedding engine: {KB_EMBEDDING_ENGINE}")
    return _embedding_model


def _normalize_vector(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(float(x) * float(x) for x in vector))
    if norm <= 0:
        return [0.0 for _ in vector]
    return [float(x) / norm for x in vector]


def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = _load_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=KB_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    output: List[List[float]] = []
    for vec in vectors:
        values = vec.tolist() if hasattr(vec, "tolist") else list(vec)
        output.append(_normalize_vector([float(v) for v in values]))
    return output


def _empty_vector() -> List[float]:
    return [0.0] * EMBEDDING_DIMENSION


def _connect_lancedb():
    global _lancedb, _db
    if _db is not None:
        return _db
    try:
        import lancedb
        _lancedb = lancedb
    except ImportError as exc:
        raise RuntimeError(
            "lancedb package not installed. Build qeeclaw-server runtime with lancedb."
        ) from exc
    _ensure_kb_dir()
    os.makedirs(_lance_dir(), exist_ok=True)
    _db = lancedb.connect(_lance_dir())
    return _db


def _table_exists(db, table_name: str) -> bool:
    try:
        return table_name in db.table_names()
    except Exception:
        return False


def _open_or_create_table():
    global _table
    if _table is not None:
        return _table
    db = _connect_lancedb()
    if _table_exists(db, KB_TABLE_NAME):
        _table = db.open_table(KB_TABLE_NAME)
        return _table
    _table = db.create_table(
        KB_TABLE_NAME,
        data=[{
            "id": "_schema",
            "doc_id": "_schema",
            "chunk_index": -1,
            "text": "",
            "filename": "",
            "doc_type": "schema",
            "scope": "_schema",
            "timestamp": 0,
            "vector": _empty_vector(),
        }],
        mode="overwrite",
    )
    try:
        _table.delete("id = '_schema'")
    except Exception:
        pass
    return _table


def _lance_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def init_knowledge_store() -> Optional[str]:
    global _kb_ready, _kb_error
    if _kb_ready:
        return _kb_error

    if KB_VECTOR_BACKEND != "lancedb":
        _kb_error = f"Unsupported local vector backend: {KB_VECTOR_BACKEND}. Expected lancedb."
        _kb_ready = True
        return _kb_error

    try:
        _ensure_kb_dir()
        _load_embedding_model()
        _open_or_create_table()
        _kb_error = None
    except Exception as e:
        _kb_error = str(e)
    _kb_ready = True
    return _kb_error


def is_kb_available() -> bool:
    if not _kb_ready:
        init_knowledge_store()
    return _kb_error is None


def get_kb_error() -> Optional[str]:
    if not _kb_ready:
        init_knowledge_store()
    return _kb_error


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > chunk_size:
                start = 0
                while start < len(para):
                    end = min(start + chunk_size, len(para))
                    chunks.append(para[start:end])
                    start = end - overlap if end < len(para) else end
            else:
                current = para

    if current:
        chunks.append(current)
    return chunks if chunks else [text[:chunk_size]] if text.strip() else []


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def add_document(
    content: str,
    filename: str = "",
    doc_type: str = "text",
    scope: str = "default",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    err = init_knowledge_store()
    if err:
        return {"success": False, "error": err}

    doc_id = str(uuid.uuid4())[:12]
    content_hash = _content_hash(content)

    meta = _load_meta()
    for existing_id, existing_doc in meta.get("documents", {}).items():
        if existing_doc.get("content_hash") == content_hash:
            return {
                "success": False,
                "error": f"Document already exists: {existing_id} ({existing_doc.get('filename', '')})",
                "existing_doc_id": existing_id,
            }

    chunks = _split_text(content)
    if not chunks:
        return {"success": False, "error": "Document is empty after processing"}

    vectors = _embed_texts(chunks)
    now = int(time.time())
    records = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        records.append({
            "id": f"{doc_id}_chunk_{i}",
            "doc_id": doc_id,
            "chunk_index": i,
            "text": chunk,
            "filename": filename,
            "doc_type": doc_type,
            "scope": scope,
            "timestamp": now,
            "vector": vector,
        })

    _open_or_create_table().add(records)

    doc_meta = {
        "doc_id": doc_id,
        "filename": filename,
        "doc_type": doc_type,
        "scope": scope,
        "tags": tags or [],
        "chunk_count": len(chunks),
        "content_hash": content_hash,
        "char_count": len(content),
        "created_at": now,
    }
    meta.setdefault("documents", {})[doc_id] = doc_meta
    _save_meta(meta)

    return {
        "success": True,
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "char_count": len(content),
    }


def delete_document(doc_id: str) -> Dict[str, Any]:
    err = init_knowledge_store()
    if err:
        return {"success": False, "error": err}

    meta = _load_meta()
    doc = meta.get("documents", {}).get(doc_id)
    if not doc:
        return {"success": False, "error": f"Document not found: {doc_id}"}

    try:
        _open_or_create_table().delete(f"doc_id = {_lance_string_literal(doc_id)}")
    except Exception:
        pass

    del meta["documents"][doc_id]
    _save_meta(meta)
    return {"success": True, "doc_id": doc_id, "chunks_removed": doc.get("chunk_count", 0)}


def list_documents(scope: Optional[str] = None) -> List[Dict[str, Any]]:
    meta = _load_meta()
    docs = list(meta.get("documents", {}).values())
    if scope:
        docs = [d for d in docs if d.get("scope") == scope]
    docs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return docs


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    meta = _load_meta()
    return meta.get("documents", {}).get(doc_id)


def search_knowledge(
    query: str,
    top_k: int = KB_TOP_K,
    scope: Optional[str] = None,
    min_score: float = MIN_SCORE_DEFAULT,
) -> List[Dict[str, Any]]:
    err = init_knowledge_store()
    if err:
        return []
    if not query.strip():
        return []

    query_vector = _embed_texts([query])[0]
    try:
        search = _open_or_create_table().search(query_vector, vector_column_name="vector").limit(top_k)
        if scope:
            search = search.where(f"scope = {_lance_string_literal(scope)}", prefilter=True)
        rows = search.to_list()
    except Exception:
        return []

    output = []
    for row in rows:
        if "_score" in row:
            score = float(row.get("_score") or 0.0)
        else:
            distance = float(row.get("_distance", 1.0))
            score = max(0.0, 1.0 - (distance / 2.0))
        if score < min_score:
            continue
        output.append({
            "text": row.get("text", ""),
            "score": round(score, 4),
            "doc_id": row.get("doc_id", ""),
            "filename": row.get("filename", ""),
            "chunk_index": row.get("chunk_index", 0),
        })
    return output


def build_rag_context(query: str, scope: Optional[str] = None) -> str:
    results = search_knowledge(query, scope=scope)
    if not results:
        return ""

    lines = ["【知识库参考资料】"]
    for i, r in enumerate(results, 1):
        source = r.get("filename") or r.get("doc_id", "")
        lines.append(f"\n--- 参考 {i} (来源: {source}, 相关度: {r['score']}) ---")
        lines.append(r["text"])

    lines.append("\n--- 参考资料结束 ---")
    lines.append("请基于以上参考资料回答用户的问题。如果参考资料不足以回答，请结合你的专业知识补充。\n")
    return "\n".join(lines)


def clear_knowledge_store() -> Dict[str, Any]:
    global _db, _table, _kb_error, _kb_ready
    _ensure_kb_dir()
    if os.path.isdir(_lance_dir()):
        shutil.rmtree(_lance_dir())
    meta_path = os.path.join(KB_DIR, _META_FILE)
    if os.path.isfile(meta_path):
        os.remove(meta_path)
    _db = None
    _table = None
    _kb_error = None
    _kb_ready = False
    init_knowledge_store()
    return {"success": True}


def get_kb_stats() -> Dict[str, Any]:
    meta = _load_meta()
    docs = meta.get("documents", {})
    total_chunks = sum(d.get("chunk_count", 0) for d in docs.values())
    total_chars = sum(d.get("char_count", 0) for d in docs.values())

    return {
        "available": is_kb_available(),
        "error": get_kb_error(),
        "storage_dir": KB_DIR,
        "vector_backend": KB_VECTOR_BACKEND,
        "vector_store_dir": _lance_dir(),
        "document_count": len(docs),
        "chunk_count": total_chunks,
        "total_chars": total_chars,
        "embedding_model": KB_EMBEDDING_MODEL,
        "embedding_model_dir": _resolve_local_model_dir() if is_kb_available() else KB_EMBEDDING_MODEL_DIR,
        "embedding_engine": _embedding_backend or KB_EMBEDDING_ENGINE,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_device": KB_DEVICE,
        "top_k": KB_TOP_K,
        "chunk_size": CHUNK_SIZE,
    }
