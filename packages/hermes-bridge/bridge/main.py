from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bridge.api.invoke import router as invoke_router
from bridge.api.invoke_compat import router as invoke_compat_router
from bridge.api.models import HealthResponse
from bridge.api.stream import router as stream_router
from bridge.api.stream_compat import router as stream_compat_router
from bridge.api.tools_list import router as tools_list_router
from bridge.config import settings
from bridge.runtime import HermesRuntime
from bridge.setup_hermes import ensure_hermes_home

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.bridge_log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    )

    logger.info("初始化 hermes home...")
    ensure_hermes_home()

    logger.info("创建 HermesRuntime (cache_max=%d)...", settings.cache_max_size)
    app.state.runtime = HermesRuntime()

    logger.info(
        "Bridge 启动: port=%d, agent_dir=%s, hermes_home=%s",
        settings.bridge_port,
        settings.hermes_agent_dir,
        settings.hermes_home,
    )
    yield

    logger.info("Bridge 关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QeeClaw Hermes Bridge",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "https://127.0.0.1:5174",
            "https://localhost:5174",
            "https://127.0.0.1:5173",
            "https://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    app.include_router(invoke_router, tags=["chat"])
    app.include_router(stream_router, tags=["chat"])
    app.include_router(invoke_compat_router, tags=["compat"])
    app.include_router(stream_compat_router, tags=["compat"])
    app.include_router(tools_list_router, tags=["tools"])

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse()

    return app


app = create_app()


def cli() -> None:
    uvicorn.run(
        "bridge.main:app",
        host="0.0.0.0",
        port=settings.bridge_port,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent)],
        log_level=settings.bridge_log_level.lower(),
    )


if __name__ == "__main__":
    cli()
