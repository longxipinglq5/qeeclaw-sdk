"""
QeeClaw Knowledge Store — 基于 ChromaDB 的本地知识库

提供文档上传、分段、向量化、检索功能。
作为 Bridge Server 的子模块运行，对 hermes-agent 零耦合。

数据存储路径：~/.qeeclaw/knowledge/  （可通过环境变量 QEECLAW_KB_DIR 覆盖）
"""

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 可选依赖（延迟导入，bridge 不强制依赖这些包）
# ---------------------------------------------------------------------------

_chromadb = None
_collection = None
_kb_ready = False
_kb_error: Optional[str] = None

KB_DIR = os.environ.get(
    "QEECLAW_KB_DIR",
    str(Path.home() / ".qeeclaw" / "knowledge"),
)

# 向量化所用的嵌入模型（ChromaDB 内置 all-MiniLM-L6-v2）
KB_EMBEDDING_MODEL = os.environ.get("QEECLAW_KB_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# 检索时返回的最大片段数
KB_TOP_K = int(os.environ.get("QEECLAW_KB_TOP_K", "5"))

# 分段参数
CHUNK_SIZE = int(os.environ.get("QEECLAW_KB_CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.environ.get("QEECLAW_KB_CHUNK_OVERLAP", "64"))

# 尝试从 config.yaml 读取配置覆盖环境变量默认值
try:
    import yaml as _yaml
    _kb_config_path = os.environ.get(
        "QEECLAW_CONFIG_FILE",
        os.path.join(os.path.dirname(__file__), "..", "..", "server", "config.yaml"),
    )
    _kb_config_path = os.path.abspath(_kb_config_path)
    if os.path.isfile(_kb_config_path):
        with open(_kb_config_path, "r", encoding="utf-8") as _f:
            _kb_cfg = (_yaml.safe_load(_f) or {}).get("knowledge", {})
        if _kb_cfg:
            _storage_dir = _kb_cfg.get("storage_dir", "")
            if _storage_dir:
                KB_DIR = os.path.expanduser(_storage_dir)
            KB_EMBEDDING_MODEL = _kb_cfg.get("embedding_model", KB_EMBEDDING_MODEL)
            KB_TOP_K = int(_kb_cfg.get("top_k", KB_TOP_K))
            CHUNK_SIZE = int(_kb_cfg.get("chunk_size", CHUNK_SIZE))
            CHUNK_OVERLAP = int(_kb_cfg.get("chunk_overlap", CHUNK_OVERLAP))
except Exception:
    pass

# 元数据索引文件
_META_FILE = "documents_meta.json"


def _ensure_kb_dir():
    os.makedirs(KB_DIR, exist_ok=True)


def _load_meta() -> Dict[str, Any]:
    """加载文档元数据索引。"""
    meta_path = os.path.join(KB_DIR, _META_FILE)
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"documents": {}}


def _save_meta(meta: Dict[str, Any]):
    """保存文档元数据索引。"""
    _ensure_kb_dir()
    meta_path = os.path.join(KB_DIR, _META_FILE)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# ChromaDB 初始化
# ---------------------------------------------------------------------------

def init_knowledge_store() -> Optional[str]:
    """
    初始化知识库（懒加载 ChromaDB）。
    返回 None 表示成功，返回错误字符串表示失败。
    """
    global _chromadb, _collection, _kb_ready, _kb_error

    if _kb_ready:
        return _kb_error

    try:
        import chromadb
        _chromadb = chromadb
    except ImportError:
        _kb_error = (
            "chromadb package not installed. "
            "Please run: pip install chromadb"
        )
        _kb_ready = True
        return _kb_error

    try:
        _ensure_kb_dir()
        client = chromadb.PersistentClient(path=os.path.join(KB_DIR, "chroma_db"))
        _collection = client.get_or_create_collection(
            name="qeeclaw_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        # Pre-warm the embedding model so the first upload doesn't hit a cold start.
        # all-MiniLM-L6-v2 is ~80 MB and takes several seconds to download and load.
        _collection.add(documents=["warmup"], ids=["_warmup"])
        _collection.delete(ids=["_warmup"])
        _kb_ready = True
        _kb_error = None
        return None
    except Exception as e:
        _kb_error = f"Failed to initialize ChromaDB: {e}"
        _kb_ready = True
        return _kb_error


def is_kb_available() -> bool:
    """知识库是否可用。"""
    if not _kb_ready:
        init_knowledge_store()
    return _kb_error is None


def get_kb_error() -> Optional[str]:
    if not _kb_ready:
        init_knowledge_store()
    return _kb_error


# ---------------------------------------------------------------------------
# 文本分段
# ---------------------------------------------------------------------------

def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    将文本按段落 + 固定长度进行分段。
    优先在自然段落边界分段，段落过长时按字符切割。
    """
    # 先按自然段落分割
    paragraphs = re.split(r'\n{2,}', text.strip())
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
            # 如果单段超长，按字符切割
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


# ---------------------------------------------------------------------------
# 文档管理
# ---------------------------------------------------------------------------

def add_document(
    content: str,
    filename: str = "",
    doc_type: str = "text",
    scope: str = "default",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    添加文档到知识库。
    - 自动分段和向量化
    - 返回 doc_id 和分段数量
    """
    err = init_knowledge_store()
    if err:
        return {"success": False, "error": err}

    doc_id = str(uuid.uuid4())[:12]
    content_hash = _content_hash(content)

    # 检查重复
    meta = _load_meta()
    for existing_id, existing_doc in meta.get("documents", {}).items():
        if existing_doc.get("content_hash") == content_hash:
            return {
                "success": False,
                "error": f"Document already exists: {existing_id} ({existing_doc.get('filename', '')})",
                "existing_doc_id": existing_id,
            }

    # 分段
    chunks = _split_text(content)
    if not chunks:
        return {"success": False, "error": "Document is empty after processing"}

    # 入库
    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "chunk_index": i,
            "filename": filename,
            "doc_type": doc_type,
            "scope": scope,
            "timestamp": str(int(time.time())),
        }
        for i in range(len(chunks))
    ]

    _collection.add(
        ids=chunk_ids,
        documents=chunks,
        metadatas=metadatas,
    )

    # 更新元数据索引
    doc_meta = {
        "doc_id": doc_id,
        "filename": filename,
        "doc_type": doc_type,
        "scope": scope,
        "tags": tags or [],
        "chunk_count": len(chunks),
        "content_hash": content_hash,
        "char_count": len(content),
        "created_at": int(time.time()),
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
    """按 doc_id 删除文档及其全部分段。"""
    err = init_knowledge_store()
    if err:
        return {"success": False, "error": err}

    meta = _load_meta()
    doc = meta.get("documents", {}).get(doc_id)
    if not doc:
        return {"success": False, "error": f"Document not found: {doc_id}"}

    # 删除 ChromaDB 中的分段
    chunk_count = doc.get("chunk_count", 0)
    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(chunk_count)]
    try:
        _collection.delete(ids=chunk_ids)
    except Exception:
        pass  # 即使向量删除失败也清理元数据

    # 删除元数据
    del meta["documents"][doc_id]
    _save_meta(meta)

    return {"success": True, "doc_id": doc_id, "chunks_removed": chunk_count}


def list_documents(scope: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出知识库中的所有文档元数据。"""
    meta = _load_meta()
    docs = list(meta.get("documents", {}).values())
    if scope:
        docs = [d for d in docs if d.get("scope") == scope]
    docs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return docs


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """获取单个文档的元数据。"""
    meta = _load_meta()
    return meta.get("documents", {}).get(doc_id)


# ---------------------------------------------------------------------------
# 向量检索（RAG 核心）
# ---------------------------------------------------------------------------

def search_knowledge(
    query: str,
    top_k: int = KB_TOP_K,
    scope: Optional[str] = None,
    min_score: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    根据查询文本检索最相关的知识片段。

    返回格式：
    [
        {
            "text": "片段文本",
            "score": 0.85,
            "doc_id": "abc123",
            "filename": "产品说明.md",
            "chunk_index": 2,
        },
        ...
    ]
    """
    err = init_knowledge_store()
    if err:
        return []

    if not query.strip():
        return []

    where_filter = None
    if scope:
        where_filter = {"scope": scope}

    try:
        results = _collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )
    except Exception:
        return []

    if not results or not results.get("documents"):
        return []

    docs_list = results["documents"][0]
    meta_list = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs_list)
    dist_list = results["distances"][0] if results.get("distances") else [1.0] * len(docs_list)

    output = []
    for text, meta, dist in zip(docs_list, meta_list, dist_list):
        # ChromaDB cosine distance → relevance score
        score = 1.0 - dist
        if score < min_score:
            continue
        output.append({
            "text": text,
            "score": round(score, 4),
            "doc_id": meta.get("doc_id", ""),
            "filename": meta.get("filename", ""),
            "chunk_index": meta.get("chunk_index", 0),
        })

    return output


def build_rag_context(query: str, scope: Optional[str] = None) -> str:
    """
    为给定的 query 构建 RAG 上下文字符串。
    直接返回可以注入到 system prompt 或 user message 的文本块。
    如果知识库为空或无相关结果，返回空字符串。
    """
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


# ---------------------------------------------------------------------------
# 知识库统计
# ---------------------------------------------------------------------------

def get_kb_stats() -> Dict[str, Any]:
    """返回知识库统计信息。"""
    meta = _load_meta()
    docs = meta.get("documents", {})
    total_chunks = sum(d.get("chunk_count", 0) for d in docs.values())
    total_chars = sum(d.get("char_count", 0) for d in docs.values())

    return {
        "available": is_kb_available(),
        "error": get_kb_error(),
        "storage_dir": KB_DIR,
        "document_count": len(docs),
        "chunk_count": total_chunks,
        "total_chars": total_chars,
        "embedding_model": KB_EMBEDDING_MODEL,
        "top_k": KB_TOP_K,
        "chunk_size": CHUNK_SIZE,
    }
