import pytest

from backend.domain import wiki_client
from backend.domain.collect_cache import PageCache, QueryCache
from backend.domain.wiki_client import WikiApiError, WikiClient, clean_snippet, page_from_parse


def test_clean_snippet_removes_tags_and_wiki_markup():
    raw = ('|proposers=[[Jessica Fridrich]]\n|year=1981?\n}}\n\'\'\'Corner Permutation\'\'\', abbrevaited '
           '\'\'\'<span class="searchmatch">CPLL</span>\'\'\', [[permute]]s the &amp; [[corner]]s')
    text = clean_snippet(raw)
    assert "<span" not in text and "searchmatch" not in text
    assert "|" not in text and "=" not in text and "[[" not in text and "'''" not in text
    assert "&amp;" not in text and "&" in text
    assert "Corner Permutation, abbrevaited CPLL, permutes the & corners" in text


def test_page_from_parse_uses_pageid_after_redirect(cpll_parse):
    page = page_from_parse(cpll_parse, lambda t: "URL:" + t)
    assert cpll_parse["parse"]["redirects"][0]["from"] == "CPLL"
    assert page["pageid"] == 1987
    assert page["title"] == "Corner Permutation of the Last Layer"
    assert page["url"] == "URL:Corner Permutation of the Last Layer"
    assert len(page["algs"]) == 33 and isinstance(page["algs"][0], dict)


@pytest.fixture
def client(monkeypatch):
    c = WikiClient()
    calls = []

    def fake_call(params):
        calls.append(params)
        if params.get("list") == "search":
            return {"query": {"search": [
                {"title": "Roux Method", "pageid": 900, "wordcount": 3,
                 "snippet": '#REDIRECT [[<span class="searchmatch">Roux</span> method]]\n'},
                {"title": "Roux method", "pageid": 58, "wordcount": 2444, "snippet": "'''Roux''' is a method"},
                {"title": "Gone", "pageid": 901, "wordcount": 2, "snippet": "#REDIRECT [[Nowhere]]"},
                {"title": "CPLL", "pageid": 1142, "wordcount": 15, "snippet": ""},   # 제목만 맞은 리다이렉트
            ]}}
        if "titles" in params:
            return {"query": {
                "redirects": [{"from": "Roux Method", "to": "Roux method"},
                              {"from": "Gone", "to": "Nowhere"},
                              {"from": "CPLL", "to": "Corner Permutation of the Last Layer"}],
                "pages": {"58": {"pageid": 58, "title": "Roux method"},
                          "1987": {"pageid": 1987, "title": "Corner Permutation of the Last Layer"},
                          "-1": {"title": "Nowhere", "missing": ""}},
            }}
        raise AssertionError(params)

    monkeypatch.setattr(c, "call", fake_call)
    c.calls = calls
    return c


def test_search_resolves_redirects_and_dedupes_by_pageid(client):
    cands = client.search("Roux")
    by_id = {c["pageid"]: c for c in cands}
    assert set(by_id) == {58, 1987}                  # 900→58 합쳐짐, 없는 문서로 가는 리다이렉트는 빠짐
    assert by_id[58]["wordcount"] == 2444 and by_id[58]["redirect_from"] is None   # 직접 검색된 쪽을 남긴다
    assert by_id[1987]["redirect_from"] == "CPLL" and by_id[1987]["wordcount"] is None
    assert set(by_id[58]) == {"title", "pageid", "wordcount", "snippet", "redirect_from"}


def test_missing_page_returns_none_without_retry(monkeypatch):
    c = WikiClient()
    calls = []

    def fake_call(params):
        calls.append(params)
        raise WikiApiError("missingtitle", "The page you specified doesn't exist.")

    monkeypatch.setattr(c, "call", fake_call)
    assert c.parse("No such page") is None
    assert len(calls) == 1


def test_fetch_page_uses_cache_for_redirect_title(tmp_path, monkeypatch, cpll_parse):
    c = WikiClient()
    calls = []
    monkeypatch.setattr(c, "call", lambda p: calls.append(p) or cpll_parse)
    cache = PageCache(tmp_path)
    first = c.fetch_page("CPLL", cache)
    again = c.fetch_page("cpll", cache)
    same = c.fetch_page("Corner Permutation of the Last Layer", cache)
    assert len(calls) == 1
    assert first["pageid"] == again["pageid"] == same["pageid"] == 1987


def test_query_cache_is_per_item(tmp_path):
    f = tmp_path / "collected_queries.json"
    qc = QueryCache(f)
    qc.mark("ssw-1987", "  PLL  Algorithms ", [1987, 109])
    assert qc.is_collected("ssw-1987", "pll algorithms")
    assert not qc.is_collected("ssw-58", "pll algorithms")   # 다른 항목은 다시 수집해야 한다
    assert QueryCache(f).is_collected("ssw-1987", "PLL algorithms")   # 파일에 저장됨


def test_retry_with_backoff(monkeypatch):
    import requests
    c = WikiClient()
    c.sleep_sec, c.backoff_base = 0, 0
    tries = []

    class Ok:
        def raise_for_status(self): pass
        def json(self): return {"ok": 1}

    def fake_get(*a, **k):
        tries.append(1)
        if len(tries) < 3:
            raise requests.ConnectionError("boom")
        return Ok()

    monkeypatch.setattr(c.session, "get", fake_get)
    monkeypatch.setattr(wiki_client.time, "sleep", lambda s: None)
    assert c.call({"action": "query"}) == {"ok": 1}
    assert len(tries) == 3
