from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class RestoreRequest(BaseModel):
    path: str


class BackupRequest(BaseModel):
    include_milvus: bool = True


def create_backup_router(backup_service, restore_service) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/backup")
    def create_backup(request: BackupRequest | None = None):
        try:
            archive = backup_service.create_backup(
                include_milvus=(
                    request.include_milvus if request is not None else True
                )
            )
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc
        return {"name": archive.name, "path": str(archive)}

    @router.get("/backup")
    def list_backups():
        return backup_service.list_backups()

    @router.post("/restore")
    def restore_backup(request: RestoreRequest):
        archive = Path(request.path)
        if not archive.exists():
            raise HTTPException(404, "Backup file not found")
        try:
            return restore_service.restore(archive)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    return router
