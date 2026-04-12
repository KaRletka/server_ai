from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # GigaChat
    gigachat_credentials: str
    gigachat_scope: str = "GIGACHAT_API_PERS"

    # Сервис
    service_api_key: str = "change_me"

    # Пути
    data_dir: Path = Path("data/connected_bases")
    logs_dir: Path = Path("logs")
    registry_file: Path = Path("bases_registry.json")


settings = Settings()
