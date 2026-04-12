from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from app.core.config import settings
from pathlib import Path


def _load_prompt(prompt_file: str) -> str:
    """Загружает системный промпт из файла."""
    path = Path("prompts") / prompt_file
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _get_client() -> GigaChat:
    return GigaChat(
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
        verify_ssl_certs=False,
    )


def generate_report(raw_data: str, report_type: str) -> str:
    """
    Отправляет сырые данные из 1С в GigaChat и возвращает готовый отчёт.

    report_type: daily | weekly | monthly | quarterly
    """
    system_prompt = _load_prompt(f"{report_type}_report.txt")

    messages = []
    if system_prompt:
        messages.append(Messages(role=MessagesRole.SYSTEM, content=system_prompt))
    messages.append(Messages(role=MessagesRole.USER, content=raw_data))

    with _get_client() as client:
        response = client.chat(Chat(messages=messages))

    return response.choices[0].message.content


def answer_prompt(user_prompt: str) -> str:
    """
    Отправляет произвольный текстовый промпт в GigaChat и возвращает ответ.
    """
    system_prompt = _load_prompt("chat.txt")

    messages = []
    if system_prompt:
        messages.append(Messages(role=MessagesRole.SYSTEM, content=system_prompt))
    messages.append(Messages(role=MessagesRole.USER, content=user_prompt))

    with _get_client() as client:
        response = client.chat(Chat(messages=messages))

    return response.choices[0].message.content
