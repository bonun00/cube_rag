import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domain.items import item_metadata, item_text, load_items
from backend.llm import MissingEnvError
from backend.service import chat
from backend.store import chroma_store
from backend.tests.conftest import BowEmbeddings, ScriptedLLM

client = TestClient(app, raise_server_exceptions=False)

RESULT = {
    "answer": "Aa 퍼뮤테이션을 쓴다 [근거 2].",
    "citations": [{"no": 2, "title": "Corner Permutation of the Last Layer", "source_type": "speedsolving_wiki", "url": "u"}],
    "players": [{"case": "Aa Permutation", "inferred": False,
                 "algs": [{"alg": "x R' U R' D2 R U' R' D2 R2 x'", "stage": "PLL", "video": None}]}],
    "no_citation": False, "notes": [], "queries": ["PLL"], "collected": [],
}


def sse_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


def post_chat(**body):
    payload = {"item_id": "ssw-1987", "question": "꼭짓점 3개?", "history": [], **body}
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return sse_events(r.text)


def test_chat_streams_progress_then_result(monkeypatch):
    def fake_ask(item_id, question, history, *, progress, use_mmr):
        assert history == [{"role": "user", "content": "안녕"}]
        progress("queries", "검색어 추출 중", {})
        progress("collect", "문서 2건 수집 중", {"count": 2})
        progress("generate", "답변 생성 중", {})
        return RESULT

    monkeypatch.setattr(chat, "ask", fake_ask)
    events = post_chat(history=[{"role": "user", "content": "안녕"}])
    assert [e for e, _ in events] == ["progress", "progress", "progress", "result"]
    assert events[1][1] == {"stage": "collect", "message": "문서 2건 수집 중", "count": 2}
    result = events[-1][1]
    assert set(result) == {"answer", "citations", "players", "no_citation", "notes"}   # 내부 값(queries 등)은 안 나감
    assert result["players"][0]["algs"][0]["stage"] == "PLL"


def test_chat_missing_env_is_friendly(monkeypatch):
    def fake_ask(*a, **k):
        raise MissingEnvError(".env에 GMS_KEY 값이 필요합니다")

    monkeypatch.setattr(chat, "ask", fake_ask)
    (event, data), = post_chat()
    assert event == "error" and data["code"] == "missing_env" and "GMS_KEY" in data["message"]


def test_chat_internal_error_hides_details(monkeypatch):
    def fake_ask(*a, **k):
        raise RuntimeError("secret sk-12345 Traceback prompt text")

    monkeypatch.setattr(chat, "ask", fake_ask)
    (event, data), = post_chat()
    assert event == "error" and data["code"] == "server_error"
    assert "sk-12345" not in json.dumps(data) and "Traceback" not in json.dumps(data)


def test_chat_unknown_item(monkeypatch):
    monkeypatch.setattr(chat, "get_runtime", lambda: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))
    (event, data), = post_chat(item_id="ssw-0")
    assert event == "error" and data["code"] == "not_found"


def test_chat_validation_error():
    r = client.post("/api/chat", json={"item_id": "ssw-1987", "question": ""})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_request"


def test_status_without_keys(tmp_chroma, monkeypatch):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"] == {"cube_meta": 0, "cube_docs": 0}
    assert body["items"] == len(load_items())
    assert isinstance(body["api_key_set"], bool)
    assert all(not v or "=" not in v for v in body["missing_env"])     # 이름만


def test_items_level_filter():
    all_items = client.get("/api/items").json()
    beginner = client.get("/api/items", params={"level": "입문"}).json()
    assert len(all_items) == len(load_items())
    assert beginner and all(x["level"] == "입문" for x in beginner)
    cpll = next(x for x in all_items if x["id"] == "ssw-1987")
    assert cpll["aliases"] == ["CPLL"] and cpll["year_uncertain"] is True
    assert "image" not in cpll


@pytest.fixture
def search_runtime(tmp_chroma, monkeypatch):
    emb = BowEmbeddings()
    meta = chroma_store.get_store("meta", emb)
    items = load_items()
    chroma_store.upsert(meta, [x["id"] for x in items], [item_text(x) for x in items], [item_metadata(x) for x in items])

    def runtime(llm):
        monkeypatch.setattr(chat, "get_runtime", lambda: SimpleNamespace(llm=llm, meta_store=meta))
        return llm
    return runtime


class PickFirstLLM(ScriptedLLM):
    """1번째 호출: 조건 파싱 응답, 2번째 호출: 후보 목록의 첫 항목 + 없는 id를 고른다."""

    def invoke(self, messages):
        if not self.replies:
            ids = [line.split(" | ")[0] for line in messages[-1].content.splitlines() if line.startswith("ssw-")]
            self.first = ids[0]
            self.replies.append(json.dumps({"items": [{"id": ids[0], "reason": "입문용이고 공식이 적다"},
                                                      {"id": "ssw-없음", "reason": "x"}]}, ensure_ascii=False))
        return super().invoke(messages)


def test_item_search_applies_filters_and_picks(search_runtime):
    llm = search_runtime(PickFirstLLM(
        json.dumps({"query": "beginner method", "filters": {"level": "입문", "algs_max": 10, "moves_max": None}}),
    ))
    r = client.post("/api/items/search", json={"condition": "공식 10개 이하인 입문 해법"})
    assert r.status_code == 200
    body = r.json()
    assert body["filters"] == {"level": "입문", "algs_max": 10}
    assert [c["id"] for c in body["cards"]] == [llm.first]              # 후보에 없는 id는 버린다
    card = body["cards"][0]
    item = next(x for x in load_items() if x["id"] == card["id"])
    assert item["level"] == "입문" and item["algs_num"] <= 10
    assert card["reason"] == "입문용이고 공식이 적다"


def test_item_search_missing_env(monkeypatch):
    def boom():
        raise MissingEnvError(".env에 GMS_KEY 값이 필요합니다")

    monkeypatch.setattr(chat, "get_runtime", boom)
    r = client.post("/api/items/search", json={"condition": "쉬운 해법"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "missing_env"
