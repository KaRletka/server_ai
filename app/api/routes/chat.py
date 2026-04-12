import logging
from fastapi import APIRouter, HTTPException
from app.core.security import authenticate_base
from app.models.schemas import ChatRequest, ChatResponse
from app.services import ai_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse, summary="Произвольный запрос к AI")
def chat(req: ChatRequest) -> ChatResponse:
    """
    Принимает текстовый промпт клиента, передаёт в GigaChat, возвращает ответ.
    """
    base_info = authenticate_base(req.credentials)
    if not base_info:
        raise HTTPException(status_code=401, detail="Неверные учётные данные базы")

    answer = ai_service.answer_prompt(req.prompt)

    logger.info(f"[{base_info.base_id}] Ответ на промпт сформирован")

    return ChatResponse(base_id=base_info.base_id, answer=answer)
