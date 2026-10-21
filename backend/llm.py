"""
LLM · 임베딩 생성 (OpenAI 호환 — SSAFY GMS). 도메인을 모르는 공통 모듈.
"""
import json
import re

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from backend.settings import get_config, get_env


class MissingEnvError(RuntimeError):
    """필수 환경변수가 비어 있다. 메시지에는 변수 이름만 담는다 (값은 절대 담지 않는다)."""


def _require(*names: str):
    missing = [n for n in get_env().missing() if n in names]
    if missing:
        raise MissingEnvError(f".env에 {', '.join(missing)} 값이 필요합니다")


def get_chat_model(**kwargs) -> ChatOpenAI:
    _require("GMS_KEY", "GMS_BASE_URL", "CHAT_MODEL")
    env = get_env()
    return ChatOpenAI(
        model=env.chat_model,
        api_key=env.gms_key,
        base_url=env.gms_base_url,
        temperature=get_config()["llm"]["temperature"],
        **kwargs,
    )


def get_embeddings() -> OpenAIEmbeddings:
    _require("GMS_KEY", "GMS_BASE_URL", "EMBED_MODEL")
    env = get_env()
    return OpenAIEmbeddings(
        model=env.embed_model,
        api_key=env.gms_key,
        base_url=env.gms_base_url,
        check_embedding_ctx_length=False,     # 토큰 배열 대신 원문 문자열로 보낸다 (호환 API 대비)
    )


def parse_json(text: str):
    """LLM 출력에서 JSON만 꺼낸다. ```json 코드 블록으로 감싸도 처리한다."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return json.loads(m.group(1) if m else text.strip())
