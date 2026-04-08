from fastapi import APIRouter

from api.v1.auth import router as auth_router
from api.v1.chapters import router as chapters_router
from api.v1.dashboard import router as dashboard_router
from api.v1.evaluation import router as evaluation_router
from api.v1.model_routing import router as model_routing_router
from api.v1.open_threads import router as open_threads_router
from api.v1.causal_graph import router as causal_graph_router
from api.v1.profile import router as profile_router
from api.v1.projects import router as projects_router
from api.v1.prompt_templates import router as prompt_templates_router
from api.v1.story_engine import router as story_engine_router
from api.v1.style_analysis import router as style_analysis_router
from api.v1.tasks import router as tasks_router
from api.v1.verification import router as verification_router
from api.v1.world_building import router as world_building_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(model_routing_router, tags=["model-routing"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(world_building_router, tags=["world-building"])
api_router.include_router(prompt_templates_router, prefix="/prompt-templates", tags=["prompt-templates"])
api_router.include_router(style_analysis_router, prefix="/style-analysis", tags=["style-analysis"])
api_router.include_router(verification_router, prefix="/verification", tags=["verification"])

# Auxiliary domain APIs still exposed for compatibility, but not current product mainline.
api_router.include_router(open_threads_router, tags=["open-threads"])
api_router.include_router(causal_graph_router, tags=["causal-graph"])

# Formal chapter chain and Story Engine remain the active product surface.
api_router.include_router(chapters_router, tags=["chapters"])
api_router.include_router(evaluation_router, tags=["evaluation"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(story_engine_router, tags=["story-engine"])
