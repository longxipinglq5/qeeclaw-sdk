from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bridge.api.billing import router as billing_router
from bridge.api.approvals import router as approvals_router
from bridge.api.automation import router as automation_router
from bridge.api.capabilities import router as capabilities_router
from bridge.api.channels import router as channels_router
from bridge.api.invoke import router as invoke_router
from bridge.api.invoke_compat import router as invoke_compat_router
from bridge.api.knowledge import router as knowledge_router
from bridge.api.memory import router as memory_router
from bridge.api.models import HealthResponse
from bridge.api.models_invoke import router as models_invoke_router
from bridge.api.models_mgmt import router as models_mgmt_router
from bridge.api.platform import router as platform_router
from bridge.api.profile_context import router as profile_context_router
from bridge.api.runs import router as runs_router
from bridge.api.sessions import router as sessions_router
from bridge.api.stream import router as stream_router
from bridge.api.stream_compat import router as stream_compat_router
from bridge.api.timeline import router as timeline_router
from bridge.api.tools_list import router as tools_list_router
from bridge.config import settings
from bridge.runtime import HermesRuntime
from bridge.runtime_facade.facade import HermesRuntimeFacade
from bridge.runtime_facade.store import check_store_readiness, warn_if_in_memory_store_multi_worker
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
    legacy_runtime = HermesRuntime()
    app.state.runtime = legacy_runtime
    app.state.runtime_facade = HermesRuntimeFacade(legacy_runtime)
    warn_if_in_memory_store_multi_worker(app.state.runtime_facade.store)
    readiness = check_store_readiness(
        app.state.runtime_facade.store,
        environment="local",
    )
    if not readiness.ready:
        raise RuntimeError(readiness.error)
    if readiness.warning:
        logger.warning(readiness.warning)

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
            "*"
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    # Facade-owned native run APIs must stay before any future legacy fallback
    # routers. Existing non-/api routes remain legacy until explicitly migrated.
    app.include_router(runs_router, tags=["runs"])
    app.include_router(automation_router, tags=["automation"])
    app.include_router(timeline_router, tags=["timeline"])
    app.include_router(approvals_router, tags=["approvals"])
    app.include_router(capabilities_router, tags=["capabilities"])
    app.include_router(invoke_router, tags=["chat"])
    app.include_router(stream_router, tags=["chat"])
    app.include_router(invoke_compat_router, tags=["compat"])
    app.include_router(stream_compat_router, tags=["compat"])
    app.include_router(tools_list_router, tags=["tools"])
    app.include_router(models_invoke_router, tags=["models"])
    app.include_router(models_mgmt_router, tags=["models"])
    app.include_router(knowledge_router, tags=["knowledge"])
    app.include_router(memory_router, tags=["memory"])
    app.include_router(sessions_router, tags=["sessions"])
    app.include_router(channels_router, tags=["channels"])
    app.include_router(billing_router, tags=["billing"])
    app.include_router(platform_router, tags=["platform"])
    app.include_router(profile_context_router, tags=["profile-context"])

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse()

    return app


app = create_app()


def cli() -> None:
    import os
    reload_enabled = os.environ.get("BRIDGE_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "bridge.main:app",
        host=settings.bridge_host,
        port=settings.bridge_port,
        reload=reload_enabled,
        reload_dirs=[str(Path(__file__).resolve().parent)] if reload_enabled else None,
        log_level=settings.bridge_log_level.lower(),
    )


if __name__ == "__main__":
    cli()
