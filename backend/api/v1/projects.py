from __future__ import annotations

from fastapi import APIRouter

from api.v1.projects_bible import router as bible_router
from api.v1.projects_bible_versions import router as bible_versions_router
from api.v1.projects_bootstrap import router as bootstrap_router
from api.v1.projects_collab import router as collab_router
from api.v1.projects_crud import router as crud_router
from api.v1.projects_generation import router as generation_router
from api.v1.projects_structure import router as structure_router


router = APIRouter()

router.include_router(crud_router, prefix="/projects")
router.include_router(bootstrap_router, prefix="/projects")
router.include_router(generation_router, prefix="/projects")
router.include_router(structure_router, prefix="/projects")
router.include_router(collab_router, prefix="/projects")
router.include_router(bible_router, prefix="/projects")
router.include_router(bible_versions_router, prefix="/projects")


__all__ = ["router"]
