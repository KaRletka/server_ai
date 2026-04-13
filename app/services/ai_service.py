import logging
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
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


def answer_prompt(user_prompt: str, credentials: BaseCredentials) -> str:
    """
    Отправляет произвольный запрос в GigaChat с доступом к инструментам 1С.

    Агентный цикл:
    1. Отправляем запрос + описание инструментов
    2. Если GigaChat вызывает инструмент — выполняем и возвращаем результат
    3. Повторяем до финального ответа или достижения лимита итераций
    """
    system_prompt = _build_system_prompt(_load_prompt("chat.txt"))

    messages: list[Messages] = []
    if system_prompt:
        messages.append(Messages(role=MessagesRole.SYSTEM, content=system_prompt))
    messages.append(Messages(role=MessagesRole.USER, content=user_prompt))

    with _get_client() as client:
        for iteration in range(settings.max_tool_iterations):
            response = client.chat(
                Chat(messages=messages, functions=ALL_TOOLS, function_call="auto")
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            assistant_message = choice.message

            # Добавляем ответ ассистента в историю
            messages.append(
                Messages(
                    role=MessagesRole.ASSISTANT,
                    content=assistant_message.content or "",
                    function_call=assistant_message.function_call,
                )
            )

            if finish_reason == "stop":
                # Финальный текстовый ответ
                return assistant_message.content

            if finish_reason == "function_call":
                tool_call = assistant_message.function_call
                tool_name = tool_call.name
                arguments = tool_call.arguments or {}

                logger.info(
                    f"GigaChat вызвал инструмент '{tool_name}' "
                    f"(итерация {iteration + 1}/{settings.max_tool_iterations})"
                )

                result = dispatch(tool_name, arguments, credentials)

                # Возвращаем результат инструмента в диалог
                messages.append(
                    Messages(
                        role=MessagesRole.FUNCTION,
                        name=tool_name,
                        content=result,
                    )
                )
                continue

            # Неожиданный finish_reason — возвращаем что есть
            logger.warning(f"Неожиданный finish_reason: {finish_reason!r}")
            return assistant_message.content or ""

    logger.warning("Достигнут лимит итераций инструментов, возвращаем последний ответ")
    return messages[-1].content or "Не удалось сформировать ответ"
