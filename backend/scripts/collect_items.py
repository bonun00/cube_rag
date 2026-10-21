"""
큐브 해법 항목 메타데이터 수집 (Speedsolving Wiki MediaWiki API)

출력: data/items.json  (항목 1건 = 인포박스가 있는 해법·단계 문서 1개)
실행: python -m backend.scripts.collect_items            # 캐시가 있으면 위키를 다시 부르지 않는다
      python -m backend.scripts.collect_items --refresh  # 위키에서 다시 받기

- 수집 카테고리: config.yaml items.categories (+ beginner_category 소속 문서도 인포박스가 있으면 추가)
- 원본 wikitext는 data/cache/item_wikitext.json 에 저장해 재파싱할 때 재호출하지 않는다
- title_ko는 data/title_ko.json (gen_title_ko.py 결과, 사람이 검수) 이 있으면 합친다
"""
import argparse
import json
import logging
from datetime import date
from urllib.parse import quote

import mwparserfromhell

from backend.domain import items as it
from backend.domain.wiki_client import WikiClient
from backend.settings import get_config, path

log = logging.getLogger(__name__)
CACHE = "item_wikitext.json"


def fetch(refresh: bool) -> dict:
    """{categories: {카테고리: [제목]}, pages: {실제 제목: {...}}, collected_at} — 캐시 우선."""
    cache = path("cache_dir") / CACHE
    if cache.exists() and not refresh:
        log.info("[캐시] %s", cache)
        return json.loads(cache.read_text(encoding="utf-8"))

    cfg = get_config()["items"]
    client = WikiClient()
    categories = {}
    for cat in cfg["categories"] + [cfg["beginner_category"]]:
        categories[cat] = [p["title"] for p in client.category_members(cat)]
        log.info("[카테고리] %s: %d건", cat, len(categories[cat]))
    titles = sorted({t for ts in categories.values() for t in ts})
    data = {
        "categories": categories,
        "pages": client.wikitext(titles),
        "collected_at": date.today().isoformat(),
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def load_title_ko() -> dict:
    f = path("items").parent / "title_ko.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def build_items(data: dict) -> tuple[list[dict], dict]:
    cfg = get_config()["items"]
    page_url = get_config()["wiki"]["page_url"]
    collected_at = data.get("collected_at") or date.today().isoformat()
    beginner = set(data["categories"][cfg["beginner_category"]])
    title_ko = load_title_ko()
    stats = {"pages": len(data["pages"]), "no_infobox": 0}

    items = []
    for title, page in sorted(data["pages"].items()):
        code = mwparserfromhell.parse(page["wikitext"])
        tpl_name, info = it.parse_infobox(code)
        if not info:
            stats["no_infobox"] += 1
            continue

        names = {title, *page["aliases"]}
        proposers_raw = info.get("proposers", "")
        if proposers_raw:
            info["proposers"] = it.split_proposers(proposers_raw)
            info["proposers_raw"] = proposers_raw

        item_id = f"ssw-{page['pageid']}"              # 리다이렉트 이후 pageid → 재색인 시 덮어쓰기
        ko = title_ko.get(item_id, {})
        source = {
            "name": "Speedsolving.com Wiki",
            "url": page_url + quote(title.replace(" ", "_")),
            "license": it.LICENSE,
            "collected_at": collected_at,
        }
        if ko.get("title_ko"):
            source["title_ko"] = it.TITLE_KO_NOTE if ko.get("reviewed") else it.TITLE_KO_NOTE_DRAFT

        items.append({
            "id": item_id,
            "title": title,
            "title_ko": ko.get("title_ko", ""),
            "level": it.LEVEL_BEGINNER if names & beginner else it.LEVEL_ADVANCED,
            "infobox_template": tpl_name,
            "infobox": info,                           # image는 메타데이터에만 — 색인 텍스트에서 제외
            "algs_num": it.first_int(info.get("algs")),
            "moves_num": it.first_int(info.get("moves")),
            "year_uncertain": "?" in info.get("year", ""),
            "summary": it.summarize(code, cfg["summary_max_chars"]),
            "source": source,
        })
    return items, stats


def save(refresh: bool = False) -> tuple[list[dict], dict]:
    items, stats = build_items(fetch(refresh))
    out = path("items")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return items, stats


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="캐시 무시하고 위키에서 다시 받기")
    args = parser.parse_args()

    items, stats = save(args.refresh)
    out = path("items")

    by_level = {lv: sum(1 for x in items if x["level"] == lv) for lv in (it.LEVEL_BEGINNER, it.LEVEL_ADVANCED)}
    print(f"\n완료: {len(items)}건 저장 → {out}")
    print(f"  수집 문서 {stats['pages']}건 중 인포박스 없음 {stats['no_infobox']}건 제외")
    print(f"  레벨: {by_level}")
    print(f"  title_ko 채워진 항목: {sum(1 for x in items if x['title_ko'])}건")


if __name__ == "__main__":
    main()
