"""知识库端点：list / stats / search / upload / delete"""

from __future__ import annotations

import logging
import os
import threading

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

_upload_lock = threading.Lock()
_MAX_UPLOAD_BYTES = int(os.environ.get("QEECLAW_KB_MAX_UPLOAD_BYTES", "0"))


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索查询文本")
    top_k: int = Field(default=5, ge=1, description="返回结果数")
    scope: str | None = Field(default=None, description="文档作用域过滤")
    min_score: float = Field(default=0.3, ge=0.0, le=1.0, description="最低相似度阈值")


@router.get("/knowledge/list")
async def knowledge_list(
    scope: str | None = Query(default=None, description="文档作用域过滤"),
):
    try:
        from knowledge_store import list_documents

        docs = list_documents(scope=scope)
        return JSONResponse({"documents": docs})
    except ImportError:
        return JSONResponse(
            {"error": "Knowledge base module not available"},
            status_code=503,
        )
    except Exception as exc:
        logger.exception("knowledge list 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/knowledge/stats")
async def knowledge_stats():
    try:
        from knowledge_store import get_kb_stats

        stats = get_kb_stats()
        return JSONResponse(stats)
    except ImportError:
        return JSONResponse(
            {
                "available": False,
                "error": (
                    "Knowledge base module not available. Build runtime with chromadb "
                    "and configure QEECLAW_KB_EMBEDDING_API_URL to an OpenAI-compatible "
                    "embeddings endpoint, e.g. http://127.0.0.1:8091/v1/embeddings."
                ),
                "document_count": 0,
            },
        )
    except Exception as exc:
        logger.exception("knowledge stats 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/knowledge/search")
async def knowledge_search(req: KnowledgeSearchRequest):
    try:
        from knowledge_store import search_knowledge

        results = search_knowledge(
            query=req.query,
            top_k=req.top_k,
            scope=req.scope,
            min_score=req.min_score,
        )
        return JSONResponse({"results": results, "count": len(results)})
    except ImportError:
        return JSONResponse(
            {
                "error": (
                    "Knowledge base module not available. Build runtime with chromadb "
                    "and configure QEECLAW_KB_EMBEDDING_API_URL."
                ),
            },
            status_code=503,
        )
    except Exception as exc:
        logger.exception("knowledge search 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/knowledge/upload")
async def knowledge_upload(request: Request):
    try:
        from knowledge_store import add_document
    except ImportError:
        return JSONResponse(
            {
                "error": (
                    "Knowledge base module not available. Build runtime with chromadb "
                    "and configure QEECLAW_KB_EMBEDDING_API_URL."
                ),
            },
            status_code=503,
        )

    try:
        content_type = request.headers.get("content-type", "")
        content_str = ""
        filename = ""
        doc_type = "text"
        scope = "default"
        tags: list[str] = []

        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file is not None:
                raw_content = await file.read()
                if _MAX_UPLOAD_BYTES > 0 and len(raw_content) > _MAX_UPLOAD_BYTES:
                    return JSONResponse(
                        {
                            "error": (
                                f"uploaded file is too large: {len(raw_content)} bytes > "
                                f"{_MAX_UPLOAD_BYTES} bytes."
                            ),
                        },
                        status_code=413,
                    )
                filename = file.filename or ""
                content_str = raw_content.decode("utf-8", errors="ignore")
            elif "content" in form:
                raw_c = form.get("content", b"")
                content_str = (
                    raw_c.decode("utf-8", errors="ignore")
                    if isinstance(raw_c, bytes)
                    else str(raw_c)
                )
                raw_name = form.get("source_name", "")
                filename = (
                    raw_name.decode("utf-8", errors="ignore")
                    if isinstance(raw_name, bytes)
                    else str(raw_name)
                )
            scope_val = form.get("scope", "default")
            scope = (
                scope_val.decode("utf-8", errors="ignore")
                if isinstance(scope_val, bytes)
                else str(scope_val)
            )
        else:
            body = await request.json()
            content = body.get("content", "")
            content_str = (
                content.decode("utf-8", errors="ignore")
                if isinstance(content, bytes)
                else str(content)
            )
            filename = body.get("filename", "")
            doc_type = body.get("doc_type", "text")
            scope = body.get("scope", "default")
            tags = body.get("tags", [])

        if not content_str:
            return JSONResponse({"error": "content or file is required"}, status_code=400)

        if not _upload_lock.acquire(blocking=False):
            return JSONResponse(
                {
                    "error": "knowledge indexing is busy; please retry after the current upload finishes",
                },
                status_code=429,
            )
        try:
            result = add_document(
                content=content_str,
                filename=filename,
                doc_type=doc_type,
                scope=scope,
                tags=tags,
            )
        finally:
            _upload_lock.release()

        if not result.get("success") and result.get("existing_doc_id"):
            result = {
                **result,
                "success": True,
                "duplicate": True,
                "doc_id": result.get("existing_doc_id"),
                "message": "文档已存在，已复用现有索引。",
            }

        status_code = 200 if result.get("success") else 400
        return JSONResponse(result, status_code=status_code)

    except Exception as exc:
        logger.exception("knowledge upload 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/knowledge/delete/{doc_id}")
async def knowledge_delete(doc_id: str):
    try:
        from knowledge_store import delete_document

        result = delete_document(doc_id)
        status_code = 200 if result.get("success") else 404
        return JSONResponse(result, status_code=status_code)
    except ImportError:
        return JSONResponse(
            {"error": "Knowledge base module not available"},
            status_code=503,
        )
    except Exception as exc:
        logger.exception("knowledge delete 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)
