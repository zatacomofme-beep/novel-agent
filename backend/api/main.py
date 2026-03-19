from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import settings
from api.ws import router as ws_router
from api.v1.router import api_router
from core.errors import AppError, ErrorDetail, ErrorResponse
from core.logging import configure_logging, get_logger
from realtime.task_events import task_event_broker


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings().log_level)
    logger.info("application_startup", extra={"env": settings().app_env})
    await task_event_broker.start()
    yield
    await task_event_broker.stop()
    logger.info("application_shutdown")


app = FastAPI(
    title=settings().app_name,
    debug=settings().app_debug,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings().api_v1_prefix)
app.include_router(ws_router, prefix="/ws")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            metadata=exc.metadata,
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(),
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": settings().app_name, "status": "bootstrapping"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready", "api_prefix": settings().api_v1_prefix}
