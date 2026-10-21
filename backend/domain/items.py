"""
큐브 해법 항목 — 인포박스 파싱(수집용), 항목 로드, 색인 텍스트·메타데이터 생성.
"""
import json
import re
from functools import lru_cache

import mwparserfromhell

from backend.settings import path

LEVEL_BEGINNER = "입문"
LEVEL_ADVANCED = "심화"
LICENSE = "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)"
TITLE_KO_NOTE = "LLM 생성 후 검수"
TITLE_KO_NOTE_DRAFT = "LLM 생성 (검수 전)"

_BR = re.compile(r"<br\s*/?>?", re.I)
_SENTENCE_END = re.compile(r"(?<!\s\d)(?<!\s\d\d)[.!?](?=\s|$)")   # "… 2." 같은 목록 번호는 문장 끝이 아님
_PROPOSER_SEP = re.compile(r"\s*(?:,|&|\band\b)\s*", re.I)


# ── 수집: 위키 문법 → 값 ────────────────────────────────────────────

def clean_value(wikitext: str) -> str:
    """인포박스 값 정제. <br>은 줄바꿈으로 바꾼 뒤 위키 문법을 걷어낸다 (그냥 지우면 이름이 붙어버린다)."""
    text = _BR.sub("\n", wikitext)
    text = re.sub(r"\]\](?=\w)", "]] ", text)           # [[이름]]설명 → 이름 설명
    text = mwparserfromhell.parse(text).strip_code()
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def parse_infobox(code) -> tuple[str | None, dict]:
    """이름에 'infobox'가 들어간 첫 템플릿의 파라미터를 dict로 뽑는다. 이름 없는 위치 인자(1, 2…)는 버린다."""
    for tpl in code.filter_templates():
        name = str(tpl.name).strip()
        if "infobox" in name.lower():
            fields = {}
            for p in tpl.params:
                key = str(p.name).strip()
                if key.isdigit():
                    continue
                val = clean_value(str(p.value))
                if val:
                    fields[key] = val
            return name, fields
    return None, {}


def split_proposers(text: str) -> list[str]:
    """줄바꿈 / 쉼표 / & / and 기준으로 제안자를 나눈다."""
    names = []
    for line in text.split("\n"):
        names += [n.strip() for n in _PROPOSER_SEP.split(line) if n.strip()]
    return names


def first_int(text: str | None) -> int | None:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def summarize(code, limit: int) -> str:
    """템플릿·표를 걷어낸 본문 앞부분. limit자를 넘으면 그 안의 마지막 문장 끝(. ! ?)까지만 남긴다."""
    text = code.strip_code().strip()
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    text = " ".join(paras)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    ends = list(_SENTENCE_END.finditer(cut))
    return cut[:ends[-1].end()] if ends else cut


# ── 사용: 항목 로드 · 색인 ──────────────────────────────────────────

@lru_cache
def load_items() -> list[dict]:
    return json.loads(path("items").read_text(encoding="utf-8"))


def get_item(item_id: str) -> dict | None:
    return next((it for it in load_items() if it["id"] == item_id), None)


def find_item(name: str) -> dict | None:
    """id · 제목 · 다른 이름(anames) · 한국어 별칭으로 찾는다 (대소문자 무시). 예: "CPLL" → Corner Permutation of the Last Layer"""
    key = name.strip().lower()
    for it in load_items():
        names = [it["id"], it["title"], it.get("title_ko") or "",
                 *re.split(r"[,\n]", it["infobox"].get("anames", ""))]
        if key in (n.strip().lower() for n in names if n):
            return it
    return None


def _one_line(text: str | None) -> str:
    return ", ".join(s.strip() for s in (text or "").split("\n") if s.strip())


def item_text(item: dict) -> str:
    """cube_meta 색인 텍스트. 이미지는 넣지 않는다. 빈 값은 건너뛴다."""
    info = item["infobox"]
    year = info.get("year", "")
    if year and item.get("year_uncertain"):
        year += " (불확실)"
    fields = [
        ("제목", item["title"]),
        ("한국어 별칭", item.get("title_ko")),
        ("다른 이름", _one_line(info.get("anames"))),
        ("제안자", ", ".join(info.get("proposers", []))),
        ("연도", year),
        ("단계 수", info.get("steps")),
        ("공식 수", _one_line(info.get("algs"))),
        ("평균 수", _one_line(info.get("moves"))),
        ("목적", _one_line(info.get("purpose"))),
        ("요약", item.get("summary")),
    ]
    return " · ".join(f"{label}: {value}" for label, value in fields if value)


def item_metadata(item: dict) -> dict:
    """cube_meta 메타데이터. 값이 없는 키는 store 쪽에서 빠진다."""
    return {
        "item_id": item["id"],
        "title": item["title"],
        "title_ko": item.get("title_ko") or "",
        "level": item["level"],
        "algs_num": item.get("algs_num"),
        "moves_num": item.get("moves_num"),
        "year": item["infobox"].get("year"),
        "source_url": item["source"]["url"],
        "source_type": "item_meta",
    }
