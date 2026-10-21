"""
API 라우터. 화면에는 API 키·프롬프트 전문·스택 트레이스를 내보내지 않는다 (서버 로그에만).

POST /api/chat 은 SSE: progress 이벤트 여러 번 → result 또는 error 이벤트 1번.
"""
import asyncio
import logging
from collections.abc import AsyncIterable

import openai
from fastapi import APIRouter, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from backend.api.schemas import (
    ChatRequest, ChatResult, ErrorEvent, Item, Progress, SearchRequest, SearchResult, Status,
)
from backend.domain.items import load_items
from backend.llm import MissingEnvError
from backend.service import chat, item_search
from backend.settings import get_env
from backend.store import chroma_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

SERVER_ERROR = "답변 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def user_error(e: Exception) -> ErrorEvent:
    """예외 → 화면용 메시지. 원인은 서버 로그에만 남긴다."""
    if isinstance(e, MissingEnvError):
        return ErrorEvent(code="missing_env", message=f"API 설정이 필요합니다. {e}")
    if isinstance(e, chat.ItemNotFound):
        return ErrorEvent(code="not_found", message="선택한 해법을 찾을 수 없습니다. 목록에서 다시 골라 주세요.")
    if isinstance(e, openai.AuthenticationError):
        return ErrorEvent(code="auth_error", message="API 키가 올바르지 않습니다. .env의 GMS_KEY를 확인해 주세요.")
    if isinstance(e, (openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError)):
        return ErrorEvent(code="llm_unavailable", message="LLM 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.")
    return ErrorEvent(code="server_error", message=SERVER_ERROR)


def log_error(e: Exception, err: ErrorEvent, what: str) -> None:
    """예상한 오류(설정 누락·없는 항목 등)는 한 줄, 그 밖의 오류는 스택 트레이스까지 서버 로그에."""
    if err.code == "server_error":
        log.exception("%s 실패", what)
    else:
        log.warning("%s 실패 [%s]: %s", what, err.code, e)


@router.get("/status", response_model=Status)
def status():
    missing = get_env().missing()
    return Status(
        counts={chroma_store.collection_name(k): chroma_store.count(k) for k in ("meta", "docs")},
        items=len(load_items()),
        api_key_set="GMS_KEY" not in missing,
        missing_env=missing,
    )


@router.get("/items", response_model=list[Item])
def items(level: str | None = None):
    out = []
    for it in load_items():
        if level and it["level"] != level:
            continue
        info = it["infobox"]
        out.append(Item(
            id=it["id"], title=it["title"], title_ko=it.get("title_ko") or "", level=it["level"],
            aliases=[a.strip() for a in info.get("anames", "").replace("\n", ",").split(",") if a.strip()],
            proposers=info.get("proposers", []), year=info.get("year"),
            year_uncertain=it.get("year_uncertain", False), steps=info.get("steps"),
            algs=info.get("algs"), algs_num=it.get("algs_num"), moves=info.get("moves"),
            purpose=[p.strip() for p in info.get("purpose", "").split("\n") if p.strip()],
            summary=it.get("summary", ""), url=it["source"]["url"],
        ))
    return out


@router.post("/chat", response_class=EventSourceResponse)
async def chat_stream(req: ChatRequest) -> AsyncIterable[ServerSentEvent]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(stage: str, message: str, data: dict) -> None:
        event = Progress(stage=stage, message=message, count=data.get("count"))
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def run() -> dict:
        return chat.ask(req.item_id, req.question, [m.model_dump() for m in req.history],
                        progress=progress, use_mmr=req.use_mmr)

    job = loop.run_in_executor(None, run)
    while True:
        getter = asyncio.ensure_future(queue.get())
        done, _ = await asyncio.wait({getter, job}, return_when=asyncio.FIRST_COMPLETED)
        if getter in done:
            yield ServerSentEvent(event="progress", data=getter.result())
            continue
        getter.cancel()
        while not queue.empty():                     # 끝나기 직전에 들어온 진행 이벤트
            yield ServerSentEvent(event="progress", data=queue.get_nowait())
        break

    try:
        result = job.result()
    except Exception as e:  # noqa: BLE001 — 어떤 예외든 화면에는 안전한 메시지만
        err = user_error(e)
        log_error(e, err, f"chat item={req.item_id}")
        yield ServerSentEvent(event="error", data=err)
        return
    yield ServerSentEvent(event="result", data=ChatResult(**result))


@router.post("/items/search", response_model=SearchResult)
def search_items(req: SearchRequest):
    try:
        rt = chat.get_runtime()
        return SearchResult(**item_search.search(req.condition, llm=rt.llm, meta_store=rt.meta_store))
    except Exception as e:  # noqa: BLE001
        err = user_error(e)
        log_error(e, err, "조건 탐색")
        raise HTTPException(status_code=503 if err.code != "server_error" else 500,
                            detail=err.model_dump()) from None
