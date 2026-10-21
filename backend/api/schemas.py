"""요청/응답 스키마."""
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    item_id: str
    question: str = Field(min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list, max_length=40)
    use_mmr: bool | None = None          # None이면 config.yaml 값


class Citation(BaseModel):
    no: int
    title: str
    source_type: str
    url: str


class PlayerAlg(BaseModel):
    alg: str
    stage: str | None
    video: str | None


class Player(BaseModel):
    case: str
    algs: list[PlayerAlg]
    inferred: bool = False               # 답변이 직접 안내하지 않았지만 질문에서 찾은 케이스라 위키 공식 목록에서 띄운 카드


class ChatResult(BaseModel):
    answer: str
    citations: list[Citation]
    players: list[Player]                # 케이스별 공식 카드 (최대 config alg_picker.max_cases)
    no_citation: bool
    notes: list[str] = []


class Progress(BaseModel):
    stage: Literal["queries", "collect", "generate"]
    message: str
    count: int | None = None             # collect 단계: 수집할 문서 수


class ErrorEvent(BaseModel):
    code: str                            # missing_env | not_found | server_error
    message: str


class Item(BaseModel):
    id: str
    title: str
    title_ko: str
    level: str
    aliases: list[str]
    proposers: list[str]
    year: str | None
    year_uncertain: bool
    steps: str | None
    algs: str | None
    algs_num: int | None
    moves: str | None
    purpose: list[str]
    summary: str
    url: str


class Status(BaseModel):
    counts: dict[str, int]               # 컬렉션 이름 → 색인 건수
    items: int
    api_key_set: bool
    missing_env: list[str]               # 비어 있는 환경변수 이름 (값은 절대 담지 않는다)


class SearchRequest(BaseModel):
    condition: str = Field(min_length=1, max_length=300)


class SearchCard(BaseModel):
    id: str
    title: str
    title_ko: str
    level: str
    algs: str | None
    moves: str | None
    reason: str


class SearchResult(BaseModel):
    cards: list[SearchCard]
    filters: dict
    notes: list[str] = []
