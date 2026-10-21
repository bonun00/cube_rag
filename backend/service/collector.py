"""
질문 시 외부 문서 수집 (RAG 파이프라인 1~4).

1. 프롬프트1 검색어 추출 + 선택 항목 문서 제목은 코드에서 항상 추가
2. 수집 캐시 확인 — (항목, 검색어)로 이미 수집한 검색어는 건너뜀
3. 위키 검색 → 길이 규칙(min_wordcount) → 프롬프트2 후보 선별. 선택 항목 자체 문서는 선별·길이 규칙과 무관하게 포함
4. 본문 수집(문서 캐시) → 청킹 → cube_docs 색인 (청크별 공식 포함). 이 항목에 이미 색인된 문서는 다시 넣지 않음
"""
import logging
from typing import Callable

from backend.domain import docs, profile
from backend.domain.collect_cache import PageCache, QueryCache, normalize_query
from backend.domain.wiki_client import WikiClient
from backend.rag import chains
from backend.settings import get_config
from backend.store import chroma_store

log = logging.getLogger(__name__)

Progress = Callable[[str, str, dict], None]


def _noop(stage: str, message: str, data: dict) -> None:
    pass


def collect(item: dict, question: str, history: list[dict] | None, *, llm, docs_store,
            client: WikiClient, qcache: QueryCache, pcache: PageCache,
            progress: Progress = _noop) -> dict:
    cfg = get_config()
    ccfg = cfg["collect"]
    item_desc = profile.describe_item(item)

    progress("queries", "검색어 추출 중", {})
    queries = chains.extract_queries(
        llm, role=profile.ROLE, rules=profile.QUERY_RULES.format(max_queries=ccfg["max_queries"]),
        item=item_desc, question=question,
        history=chains.format_history(history, cfg["chat"]["history_turns"]),
    )[:ccfg["max_queries"]]
    own_query = item["title"]
    all_queries = [own_query] + [q for q in queries if normalize_query(q) != normalize_query(own_query)]
    todo = [q for q in all_queries if not qcache.is_collected(item["id"], q)]
    result = {"queries": all_queries, "new_queries": todo, "docs": [], "candidates": 0, "notes": []}
    progress("queries", f"검색어 {len(all_queries)}개 (새로 수집 {len(todo)}개)", {"queries": all_queries, "new": todo})
    if not todo:
        progress("collect", "이미 수집한 검색어라 수집을 건너뜀", {"count": 0})
        return result

    # 3. 검색 → 선별
    candidates: dict[int, dict] = {}
    for q in todo:
        if q == own_query:
            continue                                  # 자기 문서는 검색 없이 제목으로 바로 받는다
        for c in client.search(q):
            candidates.setdefault(c["pageid"], {**c, "query": q})
    own_pageid = int(item["id"].split("-", 1)[1])
    pool = [c for c in candidates.values()
            if c["pageid"] != own_pageid and (c["wordcount"] is None or c["wordcount"] >= ccfg["min_wordcount"])]
    result["candidates"] = len(pool)
    if todo != [own_query] and not candidates:
        result["notes"].append("위키 검색 결과가 없습니다")

    selected = chains.select_docs(
        llm, role=profile.ROLE, rules=profile.SELECT_RULES, item=item_desc, question=question,
        candidates=pool, max_docs=ccfg["max_docs"],
    ) if pool else []
    targets = [(candidates[pid]["title"], candidates[pid]["query"]) for pid in selected]
    if own_query in todo:
        targets.insert(0, (item["title"], own_query))

    # 4. 본문 수집 → 색인
    progress("collect", f"문서 {len(targets)}건 수집 중", {"count": len(targets)})
    by_query: dict[str, list[int]] = {q: [] for q in todo}
    for title, q in targets:
        page = client.fetch_page(title, pcache)
        if page is None:
            log.info("없는 문서: %s", title)
            continue
        by_query[q].append(page["pageid"])
        where = {"$and": [{"item_id": item["id"]}, {"doc_id": page["pageid"]}]}
        if chroma_store.exists(docs_store, where):
            result["docs"].append({"title": page["title"], "pageid": page["pageid"], "chunks": 0, "already": True})
            continue
        ids, texts, metas = docs.chunk_records(page, item, q)
        chroma_store.upsert(docs_store, ids, texts, metas)
        result["docs"].append({"title": page["title"], "pageid": page["pageid"], "chunks": len(ids), "already": False})

    for q in todo:
        qcache.mark(item["id"], q, by_query[q])
    return result
