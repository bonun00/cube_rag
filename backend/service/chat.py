"""
질문 1건 처리: 수집(collector) → 케이스 이름 인식 → LangGraph(retrieve → generate) → 공식 선택(alg_picker).

반환: {answer, citations[{no, title, source_type, url}], players[{case, algs, inferred}], no_citation,
       notes, queries, collected}
화면용 값만 담는다 — 프롬프트·키·스택 트레이스는 넣지 않는다.

공식 카드(players)
- 질문(+검색어)에 케이스 이름이 있으면 그 케이스 청크를 근거에 고정하고, 카드도 반드시 띄운다
- LLM이 답변에서 안내한 케이스(cases)가 먼저, 질문에서 찾은 케이스가 그다음 (최대 max_cases)
- LLM이 고르지 않았는데 질문에서 찾아 띄운 카드는 inferred=True — 화면에 "위키 공식 목록에서 가져옴" 표시
"""
import logging
import threading
from dataclasses import dataclass
from functools import lru_cache

from backend.domain import alg_picker, cases, docs, profile
from backend.domain.alg_extractor import Alg
from backend.domain.collect_cache import PageCache, QueryCache
from backend.domain.items import get_item
from backend.domain.wiki_client import WikiClient
from backend.llm import get_chat_model
from backend.rag.graph import build_graph
from backend.service.collector import Progress, _noop, collect
from backend.settings import get_config
from backend.store import chroma_store

log = logging.getLogger(__name__)

# 수집 캐시 파일·위키 호출 간격을 여러 요청이 동시에 건드리지 않게 수집 구간만 한 줄로 세운다
_collect_lock = threading.Lock()


class ItemNotFound(LookupError):
    pass


@dataclass
class Runtime:
    llm: object
    meta_store: object
    docs_store: object
    graph: object
    client: WikiClient
    qcache: QueryCache
    pcache: PageCache


def make_runtime(llm=None, embeddings=None) -> Runtime:
    llm = llm or get_chat_model()
    meta_store = chroma_store.get_store("meta", embeddings)
    docs_store = chroma_store.get_store("docs", embeddings)
    graph = build_graph(llm, meta_store, docs_store, role=profile.ROLE, answer_rules=profile.ANSWER_RULES)
    return Runtime(llm, meta_store, docs_store, graph, WikiClient(), QueryCache(), PageCache())


@lru_cache
def get_runtime() -> Runtime:
    return make_runtime()


def _chunk_order(chunk_id: str) -> tuple:
    _, doc_id, n = chunk_id.rsplit(":", 2)
    return (doc_id, int(n))


def case_chunks(docs_store, item_id: str) -> dict[str, list[str]]:
    """{케이스 이름: [청크 ID…]} — 이 항목에 색인된 문서 기준, 문서 안 순서대로."""
    by_case: dict[str, list[str]] = {}
    for cid, meta in chroma_store.get_metadatas(docs_store, {"item_id": item_id}):
        case = docs.chunk_case(meta)
        if case:
            by_case.setdefault(case, []).append(cid)
    return {c: sorted(ids, key=_chunk_order) for c, ids in by_case.items()}


def pick_players(llm_cases: list[str], asked: list[str], citations: list[dict],
                 evidences: list[dict], level: str) -> list[dict]:
    """케이스별 공식 카드. 인용된 근거의 공식을 먼저, 그다음 나머지 근거 (근거 번호 순 → 문서 안 순서)."""
    limit = get_config()["alg_picker"]["max_cases"]
    wanted = list(dict.fromkeys([*llm_cases, *asked]))[:limit]
    cited_ids = {e["id"] for e in citations}
    ordered = citations + [e for e in evidences if e["id"] not in cited_ids]
    algs = [Alg.from_dict({**a, "pos": 0}) for e in ordered for a in e["algs"]]
    players = []
    for case in wanted:
        picked = alg_picker.pick(algs, case, level)
        if picked:
            players.append({
                "case": case,
                "algs": [{"alg": a.alg, "stage": a.stage, "video": a.video} for a in picked],
                "inferred": case not in llm_cases,
            })
    return players


def ask(item_id: str, question: str, history: list[dict] | None = None, *,
        progress: Progress = _noop, use_mmr: bool | None = None, runtime: Runtime | None = None) -> dict:
    item = get_item(item_id)
    if item is None:
        raise ItemNotFound(item_id)
    rt = runtime or get_runtime()
    notes = []
    if chroma_store.count("meta") == 0:
        notes.append("항목 색인이 0건입니다 (python -m backend.scripts.index_items 먼저 실행)")

    try:
        with _collect_lock:
            col = collect(item, question, history, llm=rt.llm, docs_store=rt.docs_store,
                          client=rt.client, qcache=rt.qcache, pcache=rt.pcache, progress=progress)
        notes += col["notes"]
    except RuntimeError:
        log.exception("문서 수집 실패")
        col = {"queries": [], "docs": []}
        notes.append("위키 문서 수집에 실패해 이미 색인된 문서로만 답합니다")

    # 질문(+선택 항목 제목을 뺀 검색어)에 나온 케이스 → 그 청크를 근거에 고정
    cfg = get_config()
    by_case = case_chunks(rt.docs_store, item_id)
    mention_text = " ".join([question, *col["queries"][1:]])
    asked = cases.find_cases(mention_text, list(by_case), cfg["alg_picker"]["max_cases"])
    pinned = [cid for c in asked for cid in by_case[c][:cfg["retrieve"]["pinned_per_case"]]]

    progress("generate", "답변 생성 중", {})
    state = rt.graph.invoke({
        "item_id": item_id, "question": question, "history": history or [],
        "search_queries": col["queries"], "use_mmr": use_mmr,
        "pinned_ids": pinned, "asked_cases": asked,
    })
    return {
        "answer": state["answer"],
        "citations": [{"no": e["no"], "title": e["title"], "source_type": e["source_type"], "url": e["url"]}
                      for e in state["citations"]],
        "players": pick_players(state["cases"], asked, state["citations"], state["evidences"], item["level"]),
        "no_citation": state["no_citation"],
        "notes": notes,
        "queries": col["queries"],
        "collected": [d for d in col["docs"] if not d.get("already")],
    }
