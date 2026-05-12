"""
QeeClaw Knowledge Store - local ChromaDB + llama-server embedding API.

The embedding model is a local GGUF file served by llama.cpp/llama-server.
This module does not download models and does not call cloud embedding APIs.

Default model: Qwen3-Embedding-0.6B-Q4_0.gguf
Default embedding API: http://127.0.0.1:8080/embedding
Data storage path: ~/.qeeclaw/knowledge/ by default. Override with QEECLAW_KB_DIR.
"""

import hashlib
import json
import math
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


_chromadb = None
_embedding_model = None
_embedding_backend = ""
_db = None
_collection = None
_kb_ready = False
_kb_error: Optional[str] = None
_MODULE_DIR = os.path.abspath(os.path.dirname(__file__))
_CONFIG_DIR = _MODULE_DIR

_DEFAULT_MODEL_FILE_NAME = "Qwen3-Embedding-0.6B-Q4_0.gguf"
_DEFAULT_MODEL_NAME = "Qwen3-Embedding-0.6B-Q4_0"

KB_DIR = os.environ.get(
    "QEECLAW_KB_DIR",
    str(Path.home() / ".qeeclaw" / "knowledge"),
)
KB_VECTOR_BACKEND = os.environ.get("QEECLAW_KB_VECTOR_BACKEND", "chromadb").lower()
KB_TABLE_NAME = os.environ.get("QEECLAW_KB_TABLE", "qeeclaw_knowledge")
KB_EMBEDDING_MODEL = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL", _DEFAULT_MODEL_NAME)
KB_EMBEDDING_MODEL_FILE = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL_FILE", "")
KB_EMBEDDING_MODEL_DIR = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL_DIR", "")
KB_EMBEDDING_ENGINE = os.environ.get("QEECLAW_KB_EMBEDDING_ENGINE", "llama-server").lower()
KB_EMBEDDING_API_URL = os.environ.get("QEECLAW_KB_EMBEDDING_API_URL", "http://127.0.0.1:8080/embedding")
KB_EMBEDDING_API_TIMEOUT = float(os.environ.get("QEECLAW_KB_EMBEDDING_API_TIMEOUT", "30"))
KB_CHROMA_DIR = os.environ.get("QEECLAW_KB_CHROMA_DIR", "")
KB_BATCH_SIZE = int(os.environ.get("QEECLAW_KB_EMBEDDING_BATCH_SIZE", "1"))
KB_INDEX_BATCH_SIZE = int(os.environ.get("QEECLAW_KB_INDEX_BATCH_SIZE", str(KB_BATCH_SIZE)))
KB_TOP_K = int(os.environ.get("QEECLAW_KB_TOP_K", "5"))
CHUNK_SIZE = int(os.environ.get("QEECLAW_KB_CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.environ.get("QEECLAW_KB_CHUNK_OVERLAP", "64"))
EMBEDDING_DIMENSION = int(os.environ.get("QEECLAW_KB_EMBEDDING_DIMENSION", "768"))
MIN_SCORE_DEFAULT = float(os.environ.get("QEECLAW_KB_MIN_SCORE", "0.3"))
MAX_DOCUMENT_CHARS = int(os.environ.get("QEECLAW_KB_MAX_DOCUMENT_CHARS", "200000"))
MAX_CHUNKS = int(os.environ.get("QEECLAW_KB_MAX_CHUNKS", "400"))


def _resolve_path(value: str, base_dir: str) -> str:
    if not value:
        return value
    expanded = os.path.expanduser(value)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
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
            KB_EMBEDDING_MODEL_FILE = _resolve_path(
                str(_kb_cfg.get("embedding_model_file") or KB_EMBEDDING_MODEL_FILE),
                _CONFIG_DIR,
            )
            KB_EMBEDDING_MODEL_DIR = _resolve_path(
                str(_kb_cfg.get("embedding_model_dir") or KB_EMBEDDING_MODEL_DIR),
                _CONFIG_DIR,
            )
            KB_EMBEDDING_ENGINE = str(_kb_cfg.get("embedding_engine") or KB_EMBEDDING_ENGINE).lower()
            KB_EMBEDDING_API_URL = str(_kb_cfg.get("embedding_api_url") or KB_EMBEDDING_API_URL)
            KB_EMBEDDING_API_TIMEOUT = float(
                _kb_cfg.get("embedding_api_timeout") or KB_EMBEDDING_API_TIMEOUT
            )
            KB_CHROMA_DIR = _resolve_path(str(_kb_cfg.get("chroma_dir") or KB_CHROMA_DIR), _CONFIG_DIR)
            KB_BATCH_SIZE = int(_kb_cfg.get("embedding_batch_size") or KB_BATCH_SIZE)
            KB_INDEX_BATCH_SIZE = int(_kb_cfg.get("index_batch_size") or KB_INDEX_BATCH_SIZE)
            KB_TOP_K = int(_kb_cfg.get("top_k") or KB_TOP_K)
            CHUNK_SIZE = int(_kb_cfg.get("chunk_size") or CHUNK_SIZE)
            CHUNK_OVERLAP = int(_kb_cfg.get("chunk_overlap") or CHUNK_OVERLAP)
            EMBEDDING_DIMENSION = int(_kb_cfg.get("embedding_dimension") or EMBEDDING_DIMENSION)
            MIN_SCORE_DEFAULT = float(_kb_cfg.get("min_score") or MIN_SCORE_DEFAULT)
            MAX_DOCUMENT_CHARS = int(_kb_cfg.get("max_document_chars") or MAX_DOCUMENT_CHARS)
            MAX_CHUNKS = int(_kb_cfg.get("max_chunks") or MAX_CHUNKS)
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
if "QEECLAW_KB_EMBEDDING_MODEL_FILE" in os.environ:
    KB_EMBEDDING_MODEL_FILE = _resolve_path(os.environ["QEECLAW_KB_EMBEDDING_MODEL_FILE"], _CONFIG_DIR)
if "QEECLAW_KB_EMBEDDING_MODEL_DIR" in os.environ:
    KB_EMBEDDING_MODEL_DIR = _resolve_path(os.environ["QEECLAW_KB_EMBEDDING_MODEL_DIR"], _CONFIG_DIR)
if "QEECLAW_KB_EMBEDDING_ENGINE" in os.environ:
    KB_EMBEDDING_ENGINE = os.environ["QEECLAW_KB_EMBEDDING_ENGINE"].lower()
if "QEECLAW_KB_EMBEDDING_API_URL" in os.environ:
    KB_EMBEDDING_API_URL = os.environ["QEECLAW_KB_EMBEDDING_API_URL"]
if "QEECLAW_KB_EMBEDDING_API_TIMEOUT" in os.environ:
    KB_EMBEDDING_API_TIMEOUT = float(os.environ["QEECLAW_KB_EMBEDDING_API_TIMEOUT"])
if "QEECLAW_KB_CHROMA_DIR" in os.environ:
    KB_CHROMA_DIR = _resolve_path(os.environ["QEECLAW_KB_CHROMA_DIR"], _CONFIG_DIR)
if "QEECLAW_KB_EMBEDDING_BATCH_SIZE" in os.environ:
    KB_BATCH_SIZE = int(os.environ["QEECLAW_KB_EMBEDDING_BATCH_SIZE"])
if "QEECLAW_KB_INDEX_BATCH_SIZE" in os.environ:
    KB_INDEX_BATCH_SIZE = int(os.environ["QEECLAW_KB_INDEX_BATCH_SIZE"])
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
if "QEECLAW_KB_MAX_DOCUMENT_CHARS" in os.environ:
    MAX_DOCUMENT_CHARS = int(os.environ["QEECLAW_KB_MAX_DOCUMENT_CHARS"])
if "QEECLAW_KB_MAX_CHUNKS" in os.environ:
    MAX_CHUNKS = int(os.environ["QEECLAW_KB_MAX_CHUNKS"])

if KB_VECTOR_BACKEND == "chroma":
    KB_VECTOR_BACKEND = "chromadb"
KB_BATCH_SIZE = max(1, KB_BATCH_SIZE)
KB_INDEX_BATCH_SIZE = max(1, KB_INDEX_BATCH_SIZE)
CHUNK_SIZE = max(1, CHUNK_SIZE)
CHUNK_OVERLAP = max(0, min(CHUNK_OVERLAP, CHUNK_SIZE - 1))

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


def _chroma_dir() -> str:
    if KB_CHROMA_DIR:
        return KB_CHROMA_DIR
    return os.path.join(KB_DIR, "chromadb")


def _is_gguf_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"GGUF"
    except Exception:
        return False


def _resolve_local_model_file(require: bool = False) -> str:
    candidates: List[str] = []

    def add_candidate(path: str):
        if path:
            candidates.append(path)

    add_candidate(KB_EMBEDDING_MODEL_FILE)
    if KB_EMBEDDING_MODEL_DIR:
        add_candidate(KB_EMBEDDING_MODEL_DIR)
        add_candidate(os.path.join(KB_EMBEDDING_MODEL_DIR, _DEFAULT_MODEL_FILE_NAME))
    add_candidate(os.path.join(_CONFIG_DIR, "models", _DEFAULT_MODEL_FILE_NAME))
    add_candidate(os.path.join(_MODULE_DIR, "models", _DEFAULT_MODEL_FILE_NAME))
    add_candidate(os.path.join(KB_DIR, "models", _DEFAULT_MODEL_FILE_NAME))

    searched = []
    for candidate in candidates:
        expanded = os.path.abspath(os.path.expanduser(candidate))
        if os.path.isdir(expanded):
            expanded = os.path.join(expanded, _DEFAULT_MODEL_FILE_NAME)
        searched.append(expanded)
        if os.path.isfile(expanded) and _is_gguf_file(expanded):
            return expanded

    if require:
        raise RuntimeError(
            "Local GGUF embedding model not found. Package "
            f"{_DEFAULT_MODEL_FILE_NAME} locally and set QEECLAW_KB_EMBEDDING_MODEL_FILE. "
            f"Searched: {', '.join(searched)}"
        )
    return searched[0] if searched else ""


def _is_number_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, (int, float)) for item in value)


def _extract_embedding_vector(value: Any) -> Optional[List[float]]:
    if _is_number_list(value):
        return [float(item) for item in value]

    if isinstance(value, list):
        if not value:
            return None
        # llama-server legacy endpoint may return [{"embedding": [[...]]}].
        for item in value:
            vector = _extract_embedding_vector(item)
            if vector:
                return vector
        return None

    if isinstance(value, dict):
        for key in ("embedding", "embeddings", "data"):
            if key in value:
                vector = _extract_embedding_vector(value[key])
                if vector:
                    return vector
    return None


def _embedding_base_url() -> str:
    api_url = KB_EMBEDDING_API_URL.rstrip("/")
    for suffix in ("/v1/embeddings", "/embedding"):
        if api_url.endswith(suffix):
            return api_url[: -len(suffix)]
    return api_url


def _check_embedding_api_health():
    base_url = _embedding_base_url()
    if not base_url:
        raise RuntimeError("QEECLAW_KB_EMBEDDING_API_URL is empty")
    for path in ("/health", "/v1/health"):
        try:
            with urllib.request.urlopen(base_url + path, timeout=min(KB_EMBEDDING_API_TIMEOUT, 5.0)) as response:
                if 200 <= response.status < 300:
                    return
        except Exception:
            continue
    raise RuntimeError(
        "Embedding API is not healthy. Start llama-server first, for example: "
        f"llama-server -m {_resolve_local_model_file(require=False) or _DEFAULT_MODEL_FILE_NAME} "
        "--port 8080 --embedding -t 8"
    )


class _LlamaServerEmbedder:
    def __init__(self, api_url: str, timeout: float):
        if not api_url:
            raise RuntimeError("QEECLAW_KB_EMBEDDING_API_URL is empty")
        self.api_url = api_url
        self.timeout = timeout

    def _payload_for_text(self, text: str) -> Dict[str, Any]:
        if self.api_url.rstrip("/").endswith("/v1/embeddings"):
            return {"input": text, "model": KB_EMBEDDING_MODEL}
        return {"content": text}

    def _request_embedding(self, text: str) -> List[float]:
        body = json.dumps(self._payload_for_text(text), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "qeeclaw-knowledge-store/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            raise RuntimeError(f"Embedding API returned HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"Embedding API request failed: {self.api_url} ({exc})") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Embedding API returned invalid JSON: {payload[:200]}") from exc

        vector = _extract_embedding_vector(data)
        if not vector:
            raise RuntimeError(f"Embedding API response does not contain an embedding vector: {payload[:200]}")
        return vector

    def encode(
        self,
        texts: List[str],
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ) -> List[List[float]]:
        del batch_size, show_progress_bar
        vectors = [self._request_embedding(text) for text in texts]
        if normalize_embeddings:
            return [_normalize_vector(vector) for vector in vectors]
        return vectors


def _load_embedding_model():
    global _embedding_backend, _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    engine = KB_EMBEDDING_ENGINE
    if engine == "auto":
        engine = "llama-server"

    if engine in ("llama-server", "llama_server", "llama.cpp", "llamacpp"):
        _embedding_model = _LlamaServerEmbedder(KB_EMBEDDING_API_URL, KB_EMBEDDING_API_TIMEOUT)
        _embedding_backend = "llama-server"
        return _embedding_model

    raise RuntimeError(f"Unsupported local embedding engine: {KB_EMBEDDING_ENGINE}. Expected llama-server.")


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


def _connect_chromadb():
    global _chromadb, _db
    if _db is not None:
        return _db
    try:
        import chromadb

        _chromadb = chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb package not installed. Build qeeclaw-server runtime with chromadb.") from exc

    _ensure_kb_dir()
    os.makedirs(_chroma_dir(), exist_ok=True)
    _db = chromadb.PersistentClient(path=_chroma_dir())
    return _db


def _open_or_create_collection():
    global _collection
    if _collection is not None:
        return _collection

    db = _connect_chromadb()
    try:
        _collection = db.get_collection(KB_TABLE_NAME)
        return _collection
    except Exception:
        pass

    try:
        _collection = db.create_collection(
            KB_TABLE_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        # Older Chroma versions may not accept hnsw metadata at creation time.
        _collection = db.create_collection(KB_TABLE_NAME)
    return _collection


def init_knowledge_store() -> Optional[str]:
    global _kb_ready, _kb_error
    if _kb_ready and _kb_error is None:
        return _kb_error

    if KB_VECTOR_BACKEND != "chromadb":
        _kb_error = f"Unsupported local vector backend: {KB_VECTOR_BACKEND}. Expected chromadb."
        _kb_ready = True
        return _kb_error

    try:
        _ensure_kb_dir()
        _load_embedding_model()
        _check_embedding_api_health()
        _open_or_create_collection()
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


def _format_limit_count(value: int, unit: str) -> str:
    return "unlimited" if value <= 0 else f"{value}{unit}"


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

    if MAX_DOCUMENT_CHARS > 0 and len(content) > MAX_DOCUMENT_CHARS:
        return {
            "success": False,
            "error": (
                "Document is too large for this RISC-V runtime: "
                f"{len(content)} chars > {_format_limit_count(MAX_DOCUMENT_CHARS, ' chars')}. "
                "Split the file or increase QEECLAW_KB_MAX_DOCUMENT_CHARS."
            ),
        }

    chunks = _split_text(content)
    if not chunks:
        return {"success": False, "error": "Document is empty after processing"}
    if MAX_CHUNKS > 0 and len(chunks) > MAX_CHUNKS:
        return {
            "success": False,
            "error": (
                "Document creates too many chunks for this RISC-V runtime: "
                f"{len(chunks)} chunks > {_format_limit_count(MAX_CHUNKS, ' chunks')}. "
                "Split the file, increase chunk_size, or increase QEECLAW_KB_MAX_CHUNKS."
            ),
        }

    now = int(time.time())
    collection = _open_or_create_collection()
    try:
        for offset in range(0, len(chunks), KB_INDEX_BATCH_SIZE):
            batch_chunks = chunks[offset: offset + KB_INDEX_BATCH_SIZE]
            vectors = _embed_texts(batch_chunks)
            ids = []
            documents = []
            embeddings = []
            metadatas = []
            for batch_index, (chunk, vector) in enumerate(zip(batch_chunks, vectors)):
                chunk_index = offset + batch_index
                ids.append(f"{doc_id}_chunk_{chunk_index}")
                documents.append(chunk)
                embeddings.append(vector)
                metadatas.append({
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "filename": filename,
                    "doc_type": doc_type,
                    "scope": scope,
                    "timestamp": now,
                })

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
    except Exception as exc:
        try:
            collection.delete(where={"doc_id": doc_id})
        except Exception:
            pass
        return {"success": False, "error": f"Failed to index document: {exc}"}

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
        _open_or_create_collection().delete(where={"doc_id": doc_id})
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


def _score_from_distance(distance: Any) -> float:
    try:
        score = 1.0 - float(distance)
    except Exception:
        score = 0.0
    return max(0.0, min(1.0, score))


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
        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_vector],
            "n_results": max(1, int(top_k)),
            "include": ["documents", "metadatas", "distances"],
        }
        if scope:
            query_kwargs["where"] = {"scope": scope}
        rows = _open_or_create_collection().query(**query_kwargs)
    except Exception:
        return []

    ids = (rows.get("ids") or [[]])[0] if isinstance(rows, dict) else []
    documents = (rows.get("documents") or [[]])[0] if isinstance(rows, dict) else []
    metadatas = (rows.get("metadatas") or [[]])[0] if isinstance(rows, dict) else []
    distances = (rows.get("distances") or [[]])[0] if isinstance(rows, dict) else []

    output = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
        distance = distances[index] if index < len(distances) else 1.0
        score = _score_from_distance(distance)
        if score < min_score:
            continue
        output.append({
            "text": text or "",
            "score": round(score, 4),
            "doc_id": metadata.get("doc_id", ""),
            "filename": metadata.get("filename", ""),
            "chunk_index": metadata.get("chunk_index", 0),
            "id": ids[index] if index < len(ids) else "",
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
    global _db, _collection, _kb_error, _kb_ready
    _ensure_kb_dir()
    if os.path.isdir(_chroma_dir()):
        shutil.rmtree(_chroma_dir())
    meta_path = os.path.join(KB_DIR, _META_FILE)
    if os.path.isfile(meta_path):
        os.remove(meta_path)
    _db = None
    _collection = None
    _kb_error = None
    _kb_ready = False
    init_knowledge_store()
    return {"success": True}


def get_kb_stats() -> Dict[str, Any]:
    meta = _load_meta()
    docs = meta.get("documents", {})
    total_chunks = sum(d.get("chunk_count", 0) for d in docs.values())
    total_chars = sum(d.get("char_count", 0) for d in docs.values())
    model_file = _resolve_local_model_file(require=False)

    return {
        "available": is_kb_available(),
        "error": get_kb_error(),
        "storage_dir": KB_DIR,
        "vector_backend": KB_VECTOR_BACKEND,
        "vector_store_dir": _chroma_dir(),
        "document_count": len(docs),
        "chunk_count": total_chunks,
        "total_chars": total_chars,
        "embedding_model": KB_EMBEDDING_MODEL,
        "embedding_model_file": model_file,
        "embedding_model_file_exists": bool(model_file and os.path.isfile(model_file) and _is_gguf_file(model_file)),
        "embedding_engine": _embedding_backend or KB_EMBEDDING_ENGINE,
        "embedding_api_url": KB_EMBEDDING_API_URL,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_batch_size": KB_BATCH_SIZE,
        "index_batch_size": KB_INDEX_BATCH_SIZE,
        "top_k": KB_TOP_K,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "max_document_chars": MAX_DOCUMENT_CHARS,
        "max_chunks": MAX_CHUNKS,
    }
