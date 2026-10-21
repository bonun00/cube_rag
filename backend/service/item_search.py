"""
조건 탐색 (F2011): 자연어 조건 → 검색 질의·메타 필터 → cube_meta 검색 → LLM이 조건에 맞는 항목만 선별 → 카드.

숫자 필터(algs_num 등)를 걸면 그 값이 없는 항목은 검색에서 빠진다. 필터 결과가 0건이면 숫자 필터를 풀고 한 번 더 찾는다.
"""
from backend.domain import profile
from backend.domain.items import get_item
from backend.rag import chains
from backend.settings import get_config
from backend.store import chroma_store


def build_where(filters: dict) -> dict | None:
    conds = []
    for name, value in filters.items():
        if name not in profile.FILTER_FIELDS:
            continue
        allowed = profile.FILTER_VALUES.get(name)
        if allowed is not None and value not in allowed:
            continue
        if allowed is None and not isinstance(value, (int, float)):
            continue
        key, op = profile.FILTER_FIELDS[name]
        conds.append({key: {op: value}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def search(condition: str, *, llm, meta_store) -> dict:
    parsed = chains.parse_condition(llm, role=profile.ROLE, rules=profile.FILTER_RULES, condition=condition)
    k = get_config()["item_search"]["top_k"]
    notes = []

    where = build_where(parsed["filters"])
    docs = chroma_store.search(meta_store, parsed["query"], k=k, where=where)
    if not docs and where is not None:
        loose = build_where({n: v for n, v in parsed["filters"].items() if n == "level"})
        docs = chroma_store.search(meta_store, parsed["query"], k=k, where=loose)
        notes.append("숫자 조건에 맞는 항목이 없어 조건을 넓혀 찾았습니다")

    candidates = [(d.id, d.page_content) for d in docs if d.id]
    picked = chains.pick_items(llm, role=profile.ROLE, condition=condition, candidates=candidates)
    cards = []
    for p in picked:
        item = get_item(p["id"])
        if item:
            cards.append({**profile.item_card(item), "reason": p["reason"]})
    if not cards:
        notes.append("조건에 맞는 해법을 찾지 못했습니다")
    return {"cards": cards, "filters": parsed["filters"], "notes": notes}
