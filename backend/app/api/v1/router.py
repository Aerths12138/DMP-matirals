"""Aggregate all v1 API routers."""

from fastapi import APIRouter

from app.api.v1 import (
    analysis_results,
    assistant,
    audit,
    auth,
    characterizations,
    collections,
    crystal_structures,
    dashboard,
    data_standards,
    experiments,
    files,
    materials,
    projects,
    properties,
    processing_methods,
    samples,
    search,
    tests,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(assistant.router)
api_router.include_router(users.router)
api_router.include_router(materials.router)
api_router.include_router(projects.router)
api_router.include_router(experiments.router)
api_router.include_router(samples.router)
api_router.include_router(processing_methods.router)
api_router.include_router(characterizations.router)
api_router.include_router(data_standards.router)
api_router.include_router(analysis_results.router)
api_router.include_router(properties.router)
api_router.include_router(crystal_structures.router)
api_router.include_router(files.router)
api_router.include_router(search.router)
api_router.include_router(tests.router)
api_router.include_router(collections.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
