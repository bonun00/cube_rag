"""
cube_meta 색인 — 항목 1건 = 1청크, 청크 ID = 항목 id.

실행: python -m backend.scripts.index_items

같은 ID는 덮어쓰므로 몇 번을 다시 돌려도 건수가 항목 수와 같다.
items.json에서 빠진 항목의 청크는 지운다.
"""
from backend.domain.items import item_metadata, item_text, load_items
from backend.store import chroma_store


def main(embeddings=None):
    items = load_items()
    store = chroma_store.get_store("meta", embeddings)

    before = chroma_store.count("meta")
    ids = [x["id"] for x in items]
    chroma_store.upsert(store, ids, [item_text(x) for x in items], [item_metadata(x) for x in items])

    stale = sorted(set(chroma_store.all_ids(store)) - set(ids))
    chroma_store.delete(store, stale)
    after = chroma_store.count("meta")

    print(f"cube_meta 색인: 항목 {len(items)}건 → 색인 전 {before}건 / 색인 후 {after}건 (지운 옛 항목 {len(stale)}건)")
    if after == len(items):
        print("  확인: 색인 건수 = 항목 수 (재실행해도 늘어나지 않음)")
    else:
        print("  경고: 색인 건수와 항목 수가 다르다")
    return after


if __name__ == "__main__":
    main()
