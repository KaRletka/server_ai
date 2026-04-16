import json
import logging
from openai import OpenAI
from app.core.config import settings
from app.models.schemas import BaseCredentials
from app.tools.definitions import ALL_TOOLS
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
    Отправляет произвольный запрос в OpenAI с доступом к инструментам 1С.

    Агентный цикл:
    1. Отправляем запрос + описание инструментов
    2. Если OpenAI вызывает инструменты — выполняем все и возвращаем результаты
    3. Повторяем до финального ответа или достижения лимита итераций
    """
    system_prompt = _build_system_prompt(_load_prompt("chat.txt"))
    client = _get_client()

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    for iteration in range(settings.max_tool_iterations):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        assistant_message = choice.message

        # Добавляем ответ ассистента в историю
        messages.append(assistant_message.model_dump(exclude_unset=False, exclude_none=True))

        if finish_reason == "stop":
            return assistant_message.content or ""

        if finish_reason == "tool_calls":
            # OpenAI может вернуть несколько вызовов за раз — обрабатываем все
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_call_id = tool_call.id

                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(
                    f"OpenAI вызвал инструмент '{tool_name}' "
                    f"(итерация {iteration + 1}/{settings.max_tool_iterations})"
                )

                result = dispatch(tool_name, arguments, credentials)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result,
                })
            continue

        # Неожиданный finish_reason — возвращаем что есть
        logger.warning(f"Неожиданный finish_reason: {finish_reason!r}")
        return assistant_message.content or ""

    logger.warning("Достигнут лимит итераций инструментов, возвращаем последний ответ")
    last_assistant = next(
        (m for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "assistant"),
        None,
    )
    if last_assistant:
        return last_assistant.get("content") or ""
    return "Не удалось сформировать ответ"
