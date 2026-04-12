from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.security import register_base, load_registry
from app.models.schemas import BaseCredentials, BaseInfo

router = APIRouter(prefix="/bases", tags=["bases"])


class RegisterRequest(BaseModel):
    credentials: BaseCredentials
    display_name: str = ""


@router.post("/register", response_model=BaseInfo, summary="Зарегистрировать базу 1С")
def register(req: RegisterRequest) -> BaseInfo:
    """
    Регистрирует новую базу 1С в реестре.
    Если база с таким ip+login уже есть — обновляет данные.
    """
    return register_base(req.credentials, req.display_name)


@router.get("/", summary="Список зарегистрированных баз")
def list_bases() -> list[dict]:
    """Возвращает список всех зарегистрированных баз (без паролей)."""
    registry = load_registry()
    return [
        {
            "base_id": base_id,
            "login": info["login"],
            "ip": info["ip"],
            "display_name": info.get("display_name", ""),
        }
        for base_id, info in registry.items()
    ]
