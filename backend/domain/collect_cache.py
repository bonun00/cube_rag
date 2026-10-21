"""
수집 캐시 — 같은 검색어 재수집 금지, 같은 문서 재다운로드 금지.

data/cache/collected_queries.json : {항목ID: {정규화 검색어: {collected_at, doc_ids}}}
    cube_docs는 item_id로 걸러 검색하므로, 검색어만 키로 쓰면 항목 A에서 모은 검색어를
    항목 B가 건너뛰어 B에는 문서가 0건이 된다 → (항목ID, 검색어)를 키로 쓴다.
data/cache/pages/<pageid>.json    : parse 결과 (text, algs, url…). 항목이 달라도 본문은 한 번만 받는다.
data/cache/page_titles.json       : {소문자 제목(리다이렉트 원래 제목 포함): pageid}
"""
import json
import re
from datetime import datetime
from pathlib import Path

from backend.settings import path


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q).strip().lower()


def _read(f: Path, default):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def _write(f: Path, data) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)                               # 쓰다가 죽어도 기존 파일이 깨지지 않게


class QueryCache:
    def __init__(self, file: Path | None = None):
        self.file = file or path("cache_dir") / "collected_queries.json"
        self.data: dict = _read(self.file, {})

    def is_collected(self, item_id: str, query: str) -> bool:
        return normalize_query(query) in self.data.get(item_id, {})

    def mark(self, item_id: str, query: str, doc_ids: list[int]) -> None:
        self.data.setdefault(item_id, {})[normalize_query(query)] = {
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "doc_ids": doc_ids,
        }
        _write(self.file, self.data)

    def queries(self, item_id: str) -> list[str]:
        return list(self.data.get(item_id, {}))


class PageCache:
    def __init__(self, cache_dir: Path | None = None):
        self.dir = (cache_dir or path("cache_dir")) / "pages"
        self.index_file = self.dir.parent / "page_titles.json"
        self.titles: dict = _read(self.index_file, {})

    def get(self, title: str) -> dict | None:
        pageid = self.titles.get(title.lower())
        return self.get_by_id(pageid) if pageid is not None else None

    def get_by_id(self, pageid: int) -> dict | None:
        return _read(self.dir / f"{pageid}.json", None)

    def put(self, page: dict, *requested_titles: str) -> None:
        _write(self.dir / f"{page['pageid']}.json", page)
        for t in (page["title"], *requested_titles):
            if t:
                self.titles[t.lower()] = page["pageid"]
        _write(self.index_file, self.titles)
