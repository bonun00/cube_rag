"""
수집 문서 → cube_docs 청크 레코드.

- 케이스(h2) 경계에서 먼저 나누고, 1,000자를 넘는 케이스만 다시 나눈다 → 한 청크에는 케이스가 하나뿐이다
  (그냥 1,000자로 자르면 "Ua·Ub·Z"가 한 청크에 섞이고 Z가 두 청크로 갈라졌다)
- 청크마다 그 구간의 공식을 algs(JSON 문자열)로, 케이스 이름을 case로 붙인다
"""
import json

from backend.store.chroma_store import split_with_offsets

SOURCE_WIKI = "speedsolving_wiki"
SOURCE_CUBETORIAL = "cubetorial"


def chunk_id(item_id: str, doc_id: int | str, n: int) -> str:
    return f"{item_id}:{doc_id}:{n}"


def case_sections(page: dict) -> list[tuple[int, int, str | None]]:
    """[(시작, 끝, 케이스 이름 | None)]. 케이스 구간은 그 케이스 제목 줄부터 다음 케이스 제목 줄 앞까지.

    공식이 있는 h2만 케이스로 친다 — 첫 공식 위치에서 거슬러 올라가 제목 줄("\\n<케이스>\\n")을 찾는다.
    """
    text = page["text"]
    first: dict[str, int] = {}
    for a in page.get("algs", []):
        if a.get("case") and a["case"] not in first:
            first[a["case"]] = a["pos"]

    starts: list[tuple[int, str]] = []
    for case, pos in first.items():
        h = text.rfind(f"\n{case}\n", 0, pos + 1)
        start = h + 1 if h >= 0 else pos
        if not starts or start > starts[-1][0]:
            starts.append((start, case))

    if not starts:
        return [(0, len(text), None)]
    sections = [(0, starts[0][0], None)] if starts[0][0] > 0 else []
    for i, (start, case) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        sections.append((start, end, case))
    return sections


def chunk_records(page: dict, item: dict, query: str,
                  source_type: str = SOURCE_WIKI) -> tuple[list[str], list[str], list[dict]]:
    """(ids, texts, metadatas). 청크 본문 앞에 [문서 제목 — 케이스]를 붙여 검색이 잘 되게 한다 (위치 계산은 원문 기준)."""
    ids, texts, metas = [], [], []
    text = page["text"]
    for sec_start, sec_end, case in case_sections(page):
        section = text[sec_start:sec_end]
        if not section.strip():
            continue
        for rel, chunk in split_with_offsets(section):
            start = sec_start + rel
            end = start + len(chunk)
            algs = [{k: a[k] for k in ("case", "group", "alg", "stage", "video", "order")}
                    for a in page.get("algs", []) if start <= a["pos"] < end]
            n = len(ids)
            ids.append(chunk_id(item["id"], page["pageid"], n))
            texts.append(f"[{page['title']}{f' — {case}' if case else ''}]\n{chunk}")
            metas.append({
                "doc_title": page["title"],
                "source_url": page["url"],
                "doc_id": page["pageid"],
                "item_id": item["id"],
                "item_title": item["title"],
                "query": query,
                "collected_at": page.get("collected_at", ""),
                "source_type": source_type,
                "case": case or "",
                "algs": json.dumps(algs, ensure_ascii=False),
            })
    return ids, texts, metas


def chunk_case(meta: dict) -> str | None:
    """청크의 케이스 이름. 케이스 단위로 나누기 전에 색인된 청크는 algs에서 첫 케이스를 쓴다."""
    if meta.get("case"):
        return meta["case"]
    if "case" in meta:
        return None
    algs = json.loads(meta.get("algs") or "[]")
    return next((a["case"] for a in algs if a.get("case")), None)
