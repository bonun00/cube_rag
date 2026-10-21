"""
Speedsolving.com Wiki (MediaWiki 1.43) API 호출.

호출 규칙: User-Agent에 프로젝트명·연락처, 호출 간격, 실패 시 지수 백오프 재시도.

검색 동작 (실제 응답으로 확인):
- 모든 단어가 들어간 문서만 나온다 (AND). 긴 문장은 0건 → 1~3단어 영어 키워드로 검색해야 한다
- 리다이렉트 문서도 결과에 섞인다 (예: "Roux Method" 3단어, snippet "#REDIRECT [[...]]")
  → 대상 문서로 풀어서 리다이렉트 이후 pageid로 중복을 없앤다
"""
import html
import logging
import re
import time
from urllib.parse import quote

import mwparserfromhell
import requests

from backend.domain.alg_extractor import extract
from backend.settings import get_config, get_env

log = logging.getLogger(__name__)

FALLBACK_USER_AGENT = "CubeRAG/0.1 (SSAFY AI project)"

_TAG = re.compile(r"<[^>]+>")
_REDIRECT = re.compile(r"^\s*#REDIRECT\s*\[\[([^\]|#]+)", re.I)
_PARAM_KEY = re.compile(r"\|\s*[\w ]+?\s*=\s*")


def clean_snippet(snippet: str) -> str:
    """검색 snippet 정제: 태그 제거 → html.unescape → strip_code → `|key=` 잔여 제거."""
    text = html.unescape(_TAG.sub("", snippet))
    text = mwparserfromhell.parse(text).strip_code()
    text = _PARAM_KEY.sub(" ", text)
    text = re.sub(r"\{\{|\}\}|\[\[|\]\]|'''|''", "", text)    # 잘린 템플릿·링크 조각
    return re.sub(r"\s+", " ", text).strip()


def page_from_parse(data: dict, url_of) -> dict:
    """action=parse 응답 → 수집 문서. 텍스트와 공식은 같은 HTML 순회에서 뽑아 공식 위치가 텍스트 기준으로 맞는다."""
    p = data["parse"]
    content = extract(p["text"]["*"])
    return {
        "pageid": p["pageid"],                    # 리다이렉트 이후 문서 ID — 중복 색인 방지
        "title": p["title"],
        "url": url_of(p["title"]),
        "text": content.text,
        "algs": [a.to_dict() for a in content.algs],
    }


class WikiApiError(RuntimeError):
    """API가 error 응답을 돌려줌 (없는 문서 등) — 재시도해도 같으므로 바로 올린다."""

    def __init__(self, code: str, info: str):
        super().__init__(f"{code}: {info}")
        self.code = code

class WikiClient:
    def __init__(self):
        cfg = get_config()["wiki"]
        self.api_url = cfg["api_url"]
        self.page_url_prefix = cfg["page_url"]
        self.sleep_sec = cfg["sleep_sec"]
        self.max_retry = cfg["max_retry"]
        self.backoff_base = cfg["backoff_base_sec"]
        self.timeout = cfg["timeout_sec"]

        user_agent = get_env().wiki_user_agent
        if not user_agent:
            log.warning("WIKI_USER_AGENT가 비어 있어 연락처 없는 User-Agent로 호출한다. .env에 채워 넣을 것")
            user_agent = FALLBACK_USER_AGENT
        user_agent.encode("latin-1")    # HTTP 헤더 — 한글이 있으면 여기서 실패한다

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_call = 0.0

    def call(self, params: dict) -> dict:
        """API 1회 호출. 직전 호출과 sleep_sec 간격을 두고, 실패하면 backoff_base * 2^n 초 쉬고 재시도한다."""
        params = {**params, "format": "json"}
        for attempt in range(1, self.max_retry + 1):
            wait = self.sleep_sec - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.session.get(self.api_url, params=params, timeout=self.timeout)
                self._last_call = time.monotonic()
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError) as e:
                self._last_call = time.monotonic()
                log.warning("위키 호출 실패 %d/%d: %s", attempt, self.max_retry, e)
                if attempt < self.max_retry:
                    time.sleep(self.backoff_base * 2 ** (attempt - 1))
                continue
            if "error" in data:
                raise WikiApiError(data["error"].get("code", ""), data["error"].get("info", ""))
            return data
        raise RuntimeError(f"위키 API 호출 실패: {params.get('action')} {params.get('list') or params.get('page') or ''}")

    def page_url(self, title: str) -> str:
        return self.page_url_prefix + quote(title.replace(" ", "_"))

    def search(self, query: str, limit: int | None = None) -> list[dict]:
        """후보 문서 [{title, pageid, wordcount, snippet, redirect_from}] — 리다이렉트를 풀고 pageid로 중복 제거.

        리다이렉트로 들어온 후보는 대상 문서의 wordcount를 모르므로 None (같은 문서가 직접 검색되면 그쪽 값을 쓴다).
        """
        data = self.call({
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": limit or get_config()["collect"]["srlimit"], "srprop": "snippet|wordcount",
        })
        raw = data["query"]["search"]
        if not raw:
            return []
        # 제목만 맞아 snippet이 빈 리다이렉트도 있다 (예: "CPLL") → snippet이 아니라 제목을 전부 풀어 본다
        resolved = self._resolve([r["title"] for r in raw])

        by_id: dict[int, dict] = {}
        for r in raw:
            target = resolved.get(r["title"])
            if not target:
                continue                                 # 없는 문서로 가는 리다이렉트
            if target["title"] != r["title"] or _REDIRECT.match(_TAG.sub("", r.get("snippet", ""))):
                cand = {**target, "wordcount": None, "snippet": "", "redirect_from": r["title"]}
            else:
                cand = {"title": r["title"], "pageid": r["pageid"], "wordcount": r.get("wordcount"),
                        "snippet": clean_snippet(r.get("snippet", "")), "redirect_from": None}
            prev = by_id.get(cand["pageid"])
            if prev is None or (prev["redirect_from"] and not cand["redirect_from"]):
                by_id[cand["pageid"]] = cand              # 직접 검색된 쪽(실제 wordcount·snippet)을 남긴다
        return list(by_id.values())

    def _resolve(self, titles: list[str]) -> dict[str, dict]:
        """{요청 제목: {title, pageid}} — 리다이렉트를 따라간 실제 문서. 없는 문서는 빠진다."""
        data = self.call({"action": "query", "titles": "|".join(titles[:50]), "redirects": 1})
        q = data["query"]
        target = {t: t for t in titles}
        for key in ("normalized", "redirects"):
            hops = {m["from"]: m["to"] for m in q.get(key, [])}
            target = {t: hops.get(cur, cur) for t, cur in target.items()}
        pages = {p["title"]: p for p in q["pages"].values() if "missing" not in p}
        return {t: {"title": cur, "pageid": pages[cur]["pageid"]} for t, cur in target.items() if cur in pages}

    def fetch_page(self, title: str, cache=None) -> dict | None:
        """본문 수집 (PageCache가 있으면 캐시 우선). 같은 문서를 리다이렉트 제목으로 불러도 한 번만 받는다."""
        if cache is not None:
            hit = cache.get(title)
            if hit:
                return hit
        page = self.parse(title)
        if page is not None:
            page["collected_at"] = time.strftime("%Y-%m-%d")
            if cache is not None:
                cache.put(page, title)
        return page

    def parse(self, title: str) -> dict | None:
        """본문 수집. {pageid(리다이렉트 이후), title, url, text, algs} — 없는 문서면 None."""
        try:
            data = self.call({"action": "parse", "page": title, "prop": "text", "redirects": 1})
        except WikiApiError as e:
            if e.code == "missingtitle":
                return None
            raise
        return page_from_parse(data, self.page_url)

    def category_members(self, category: str) -> list[dict]:
        """카테고리의 일반 문서(ns=0)만 가져온다. 하위 카테고리는 제외."""
        pages, cont = [], {}
        while True:
            data = self.call({
                "action": "query", "list": "categorymembers",
                "cmtitle": category, "cmlimit": 500, "cmnamespace": 0, **cont,
            })
            pages += data["query"]["categorymembers"]
            if "continue" not in data:
                return pages
            cont = data["continue"]

    def wikitext(self, titles: list[str]) -> dict[str, dict]:
        """50개씩 묶어 본문 wikitext를 가져온다. 리다이렉트를 따라간 뒤의 문서 기준.

        반환: {실제 제목: {pageid, title, aliases(이 문서로 넘어온 요청 제목들), wikitext}}
        CPLL → Corner Permutation of the Last Layer 처럼 두 제목이 한 문서로 모이면 1건이 된다.
        """
        result = {}
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            data = self.call({
                "action": "query", "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "titles": "|".join(batch), "redirects": 1,
            })
            q = data["query"]
            target = {t: t for t in batch}               # 요청 제목 → 실제 제목
            for key in ("normalized", "redirects"):
                hops = {m["from"]: m["to"] for m in q.get(key, [])}
                target = {t: hops.get(cur, cur) for t, cur in target.items()}
            for page in q["pages"].values():
                revs = page.get("revisions")
                if not revs:
                    continue
                entry = result.setdefault(page["title"], {
                    "pageid": page["pageid"],
                    "title": page["title"],
                    "aliases": [],
                    "wikitext": revs[0]["slots"]["main"]["*"],
                })
                entry["aliases"] += [t for t, cur in target.items()
                                     if cur == page["title"] and t != page["title"]]
            log.info("본문 %d/%d", min(i + 50, len(titles)), len(titles))
        return result
