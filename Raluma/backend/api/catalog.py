import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from engine.pdf import ASSETS_DIR

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/profile-assets/{filename}")
def get_profile_asset(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(ASSETS_DIR, safe_name)
    if safe_name != filename or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    return FileResponse(path)
