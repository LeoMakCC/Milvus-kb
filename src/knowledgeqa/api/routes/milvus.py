from __future__ import annotations

from fastapi import APIRouter


def create_milvus_router(docker_controller) -> APIRouter:
    router = APIRouter(prefix="/api/v1/milvus")

    @router.get("/status")
    def status():
        return {
            "available": docker_controller.is_available(),
            "running": docker_controller.is_running(),
            "compose_status": "ok",
        }

    @router.post("/start")
    def start():
        result = docker_controller.compose_up()
        return {"returncode": result.returncode}

    @router.post("/stop")
    def stop():
        result = docker_controller.compose_down()
        return {"returncode": result.returncode}

    return router
