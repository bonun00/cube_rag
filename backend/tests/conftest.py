import hashlib
import json
import re
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage

from backend.settings import get_config
from backend.store import chroma_store

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class BowEmbeddings(Embeddings):
    """단어 해시 임베딩 — 네트워크 없이 검색 동작 확인용."""

    def _v(self, t):
        v = [0.0] * 128
        for w in re.findall(r"\w+", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 128] += 1
        n = sum(x * x for x in v) ** .5 or 1
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._v(t) for t in texts]

    def embed_query(self, text):
        return self._v(text)


class ScriptedLLM:
    """정해 둔 응답을 차례로 돌려주는 가짜 LLM."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        return AIMessage(content=self.replies.pop(0))


@pytest.fixture
def tmp_chroma(tmp_path, monkeypatch):
    """Vector DB를 임시 폴더로 — 실제 data/chroma는 건드리지 않는다."""
    cfg = get_config()
    monkeypatch.setitem(cfg["paths"], "chroma_dir", str(tmp_path / "chroma"))
    chroma_store.get_client.cache_clear()
    yield
    chroma_store.get_client.cache_clear()


@pytest.fixture
def cpll_parse() -> dict:
    """CPLL 문서 action=parse 응답 저장본 (리다이렉트 → Corner Permutation of the Last Layer)."""
    return load_fixture("parse_cpll.json")


@pytest.fixture
def pll_parse() -> dict:
    return load_fixture("parse_pll.json")
