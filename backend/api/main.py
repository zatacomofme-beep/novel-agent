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
LEGACY_CHAPTER_ROUTE_PREFIX = f"{settings().api_v1_prefix}/chapters/"
LEGACY_CHAPTER_SUNSET = "Wed, 31 Dec 2026 23:59:59 GMT"


def _legacy_chapter_routes_mode() -> str:
    mode = (settings().legacy_chapter_routes_mode or "compat").strip().lower()
    if mode == "gone":
        return "gone"
    return "compat"


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

_cors_origins: list[str] = []
_raw_origins = getattr(settings, "cors_allowed_origins", None)
if _raw_origins:
    if isinstance(_raw_origins, str):
        _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    elif isinstance(_raw_origins, list):
        _cors_origins = _raw_origins

if not _cors_origins and settings().app_env == "development":
    logger.warning(
        "cors_allowing_all_origins_in_dev",
        extra={"message": "CORS allowing all origins in development mode"},
    )
    _cors_origins = ["*"]

if "*" in _cors_origins and settings().app_env == "production":
    logger.error(
        "cors_wildcard_in_production",
        extra={
            "message": "CORS wildcard (*) is dangerous in production with credentials enabled"
        },
    )
    _cors_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],
    allow_credentials=len(_cors_origins) > 0 and "*" not in _cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
)


@app.middleware("http")
async def add_legacy_chapter_deprecation_headers(request: Request, call_next):
    is_legacy_chapter_path = request.url.path.startswith(LEGACY_CHAPTER_ROUTE_PREFIX)
    if is_legacy_chapter_path and _legacy_chapter_routes_mode() == "gone":
        logger.warning(
            "legacy_chapter_endpoint_blocked",
            extra={"path": request.url.path},
        )
        payload = ErrorResponse(
            error=ErrorDetail(
                code="chapter.legacy_endpoint_gone",
                message=(
                    "Legacy chapter endpoints are no longer available. "
                    "Use project-scoped story-engine chapter routes."
                ),
                metadata={"path": request.url.path},
            )
        )
        response = JSONResponse(status_code=410, content=payload.model_dump())
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = LEGACY_CHAPTER_SUNSET
        return response

    response = await call_next(request)
    if is_legacy_chapter_path:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = LEGACY_CHAPTER_SUNSET
    return response


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


@app.get("/metrics")
async def metrics():
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return {"error": "prometheus_client not installed"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready", "api_prefix": settings().api_v1_prefix}
