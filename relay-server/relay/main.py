# termhop relay — FastAPI app entrypoint. Run via:
#   uvicorn relay.main:app --host 0.0.0.0 --port 8080
from contextlib import asynccontextmanager

from fastapi import FastAPI

from relay.config import Config
from relay.redis_client import make_redis
from relay.session_registry import SessionRegistry
from relay.ws_handlers import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    app.state.config = cfg
    app.state.redis = make_redis(cfg.redis_url)
    app.state.registry = SessionRegistry()
    try:
        yield
    finally:
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(ws_router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
