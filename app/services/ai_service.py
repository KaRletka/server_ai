import json
import logging
from openai import OpenAI
from app.core.config import settings
from app.models.schemas import BaseCredentials
from app.tools.executor import dispatch
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_prompt(prompt_file: str) -> str:
    """Загружает системный промпт из файла."""
    path = Path("prompts") / prompt_file
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_knowledge_base() -> str:
    """Загружает базу знаний из файла. Возвращает пустую строку если файл не найден."""
    path = settings.knowledge_base_file
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _build_system_prompt(base_prompt: str) -> str:
    """Формирует итоговый системный промпт с базой знаний."""
    knowledge_base = _load_knowledge_base()
    if not knowledge_base:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        f"=== БАЗА ЗНАНИЙ ===\n"
        f"{knowledge_base}\n"
        f"==================="
    )


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def generate_report(raw_data: str, report_type: str) -> str:
    """
    Отправляет сырые данные из 1С в OpenAI и возвращает готовый отчёт.

    report_type: daily | weekly | monthly | quarterly
    """
    system_prompt = _load_prompt(f"{report_type}_report.txt")

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": raw_data})

    client = _get_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
    )
    return response.choices[0].message.content


def answer_prompt(user_prompt: str, credentials: BaseCredentials) -> str:
    """
    Отправляет запрос через OpenAI Assistants API (Threads + Runs).
    Если ассистент вызывает инструменты 1С (requires_action) — выполняем их
    и возвращаем результаты обратно до получения финального ответа.
    """
    client = _get_client()

    thread = client.beta.threads.create(
        tool_resources={"file_search": {"vector_store_ids": [settings.openai_vector_store_id]}}
    )

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_prompt,
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=settings.openai_assistant_id,
        additional_instructions=_load_prompt("chat.txt"),
    )

    while run.status == "requires_action":
        tool_outputs = []
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            logger.info(f"Ассистент вызвал инструмент '{tool_name}'")
            result = dispatch(tool_name, arguments, credentials)
            tool_outputs.append({"tool_call_id": tool_call.id, "output": result})

        run = client.beta.threads.runs.submit_tool_outputs_and_poll(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )

    if run.status != "completed":
        logger.error(f"Run завершился со статусом: {run.status}, ошибка: {run.last_error}")
        raise RuntimeError(f"Run failed: {run.status} — {run.last_error}")

    messages = client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=1)
    return messages.data[0].content[0].text.value
