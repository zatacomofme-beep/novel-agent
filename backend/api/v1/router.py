from fastapi import APIRouter

from api.v1.auth import router as auth_router
from api.v1.chapters import router as chapters_router
from api.v1.dashboard import router as dashboard_router
from api.v1.evaluation import router as evaluation_router
from api.v1.model_routing import router as model_routing_router
from api.v1.profile import router as profile_router
from api.v1.projects import router as projects_router
from api.v1.story_engine import router as story_engine_router
from api.v1.tasks import router as tasks_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(model_routing_router, tags=["model-routing"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(chapters_router, tags=["chapters"])
api_router.include_router(evaluation_router, tags=["evaluation"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(story_engine_router, tags=["story-engine"])
