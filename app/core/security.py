import hashlib
import json
from pathlib import Path
from app.core.config import settings
from app.models.schemas import BaseCredentials, BaseInfo


def make_base_id(credentials: BaseCredentials) -> str:
    """Генерирует уникальный идентификатор базы из ip + login."""
    raw = f"{credentials.ip}_{credentials.login}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_registry() -> dict:
    """Загружает реестр баз из JSON-файла."""
    if not settings.registry_file.exists():
        return {}
    with open(settings.registry_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    """Сохраняет реестр баз в JSON-файл."""
    with open(settings.registry_file, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def authenticate_base(credentials: BaseCredentials) -> BaseInfo | None:
    """
    Проверяет учётные данные базы.
    Возвращает BaseInfo если база зарегистрирована и пароль совпадает,
    иначе None.
    """
    registry = load_registry()
    base_id = make_base_id(credentials)

    if base_id not in registry:
        return None

    entry = registry[base_id]
    if entry["password"] != credentials.password:
        return None

    return BaseInfo(
        base_id=base_id,
        login=entry["login"],
        ip=entry["ip"],
        display_name=entry.get("display_name", ""),
    )


def register_base(credentials: BaseCredentials, display_name: str = "") -> BaseInfo:
    """
    Регистрирует новую базу или обновляет существующую.
    Возвращает BaseInfo.
    """
    registry = load_registry()
    base_id = make_base_id(credentials)

    registry[base_id] = {
        "login": credentials.login,
        "password": credentials.password,
        "ip": credentials.ip,
        "display_name": display_name,
    }

    save_registry(registry)
    return BaseInfo(base_id=base_id, login=credentials.login, ip=credentials.ip, display_name=display_name)
