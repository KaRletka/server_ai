import json
import logging
from openai import OpenAI
from app.core.config import settings
from app.models.schemas import BaseCredentials
from pathlib import Path

from app.services.onec_service import execute_query

logger = logging.getLogger(__name__)


def _load_prompt(prompt_file: str) -> str:
    path = Path("prompts") / prompt_file
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


# =========================
# 📊 REPORT GENERATION
# =========================
def generate_report(raw_data: str, report_type: str) -> str:
    system_prompt = _load_prompt(f"{report_type}_report.txt")

    client = _get_client()

    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_data},
        ],
    )

    return response.output_text or ""


# =========================
# 💬 CHAT (без dispatch)
# =========================
def answer_prompt(user_prompt: str, credentials: BaseCredentials) -> str:
    client = _get_client()

    system_prompt = _load_prompt("chat.txt")

    # 🔥 теперь инструменты напрямую
    tools = [
        {
            "type": "file_search",
            "vector_store_ids": [settings.openai_vector_store_id],
        },
        {
            "type": "function",
            "name": "execute_1c_query",
            "description": "Выполняет запрос к базе 1С и возвращает данные",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL или 1С-запрос"
                    }
                },
                "required": ["query"],
            },
        },
        {
            "type": "function",
            "name": "get_balance",
            "description": "Получает баланс по контрагенту",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "ID клиента"
                    }
                },
                "required": ["client_id"],
            },
        }
    ]

    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
        )

        # 🔁 tool loop
        for _ in range(5):
            tool_calls = [
                item for item in response.output
                if item.type == "function_call"
            ]

            if not tool_calls:
                break

            for tool_call in tool_calls:
                tool_name = tool_call.name

                try:
                    args = json.loads(tool_call.arguments or "{}")
                except Exception:
                    logger.exception("Ошибка парсинга arguments")
                    args = {}

                logger.info(f"Вызов инструмента: {tool_name} | args: {args}")

                # 🔥 прямая маршрутизация
                try:
                    if tool_name == "execute_1c_query":
                        result = _execute_1c_query(args, credentials)

                    elif tool_name == "get_balance":
                        result = _get_balance(args, credentials)

                    else:
                        logger.error(f"Неизвестный инструмент: {tool_name}")
                        result = "Неизвестный инструмент"

                except Exception as e:
                    logger.exception(f"Ошибка выполнения инструмента {tool_name}")
                    result = {
                        "status": "error",
                        "type": "tool_runtime_error",
                        "message": str(e)
                    }

                response = client.responses.create(
                    model=settings.openai_model,
                    input=[
                        {
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": json.dumps(result, ensure_ascii=False),
                        }
                    ],
                    previous_response_id=response.id,
                )

        return response.output_text or "Не удалось получить ответ"

    except Exception:
        logger.exception("Ошибка при работе с OpenAI API")
        return "Ошибка обработки запроса"


# =========================
# 🔧 TOOL IMPLEMENTATIONS
# =========================

def _execute_1c_query(args: dict, credentials: BaseCredentials):
    query = args.get("query")

    if not query:
        return "Ошибка: query не передан"

    logger.info(f"[TOOL] execute_1c_query: {query}")

    try:
        result = execute_query(credentials, query)

        logger.info(f"[TOOL RESULT] {result}")

        return result  # 🔥 важно: вернуть dict или строку

    except Exception as e:
        logger.exception("Ошибка при выполнении запроса к 1С")
        return {
            "status": "error",
            "message": str(e),
            "type": "1c_query_error"
        }


def _get_balance(args: dict, credentials: BaseCredentials):
    client_id = args.get("client_id")

    if not client_id:
        return "Ошибка: client_id не передан"

    # 👉 здесь реальный вызов 1С
    logger.info(f"GET BALANCE: {client_id}")

    return f"Баланс клиента {client_id}: 1000"