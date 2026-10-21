"""
cube_docs 다시 색인 — 청킹 방식을 바꾼 뒤 이미 수집한 문서를 새 방식으로 다시 넣는다.

실행: python -m backend.scripts.reindex_docs

- 위키를 다시 부르지 않는다: 지금 cube_docs에 있는 (항목, 문서) 쌍을 data/cache/pages 의 본문 캐시로 다시 청킹한다
- 수집 기록(collected_queries.json)은 그대로 둔다
- (항목, 문서)마다 옛 청크를 지우고 새 청크를 넣는다 → 청크 수가 줄어도 옛 청크가 남지 않는다
"""
from backend.domain import docs
from backend.domain.collect_cache import PageCache
from backend.domain.items import get_item
from backend.store import chroma_store


def main(embeddings=None):
    store = chroma_store.get_store("docs", embeddings)
    pages = PageCache()
    before = chroma_store.count("docs")

    pairs: dict[tuple[str, int], str] = {}
    for _, meta in chroma_store.get_metadatas(store, {"source_type": docs.SOURCE_WIKI}):
        pairs.setdefault((meta["item_id"], meta["doc_id"]), meta.get("query", ""))

    done, skipped = 0, []
    for (item_id, doc_id), query in sorted(pairs.items()):
        item, page = get_item(item_id), pages.get_by_id(doc_id)
        if item is None or page is None:
            skipped.append(f"{item_id}:{doc_id}")
            continue
        where = {"$and": [{"item_id": item_id}, {"doc_id": doc_id}]}
        chroma_store.delete(store, chroma_store.all_ids(store, where))
        chroma_store.upsert(store, *docs.chunk_records(page, item, query))
        done += 1
        print(f"  {item_id} · {page['title']}")

    after = chroma_store.count("docs")
    print(f"\ncube_docs 다시 색인: 문서 {done}건, 청크 {before}건 → {after}건")
    if skipped:
        print(f"  건너뜀 (항목 또는 본문 캐시 없음): {skipped}")


if __name__ == "__main__":
    main()
