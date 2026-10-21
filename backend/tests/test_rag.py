import json

from backend.domain import docs
from backend.domain.wiki_client import page_from_parse
from backend.rag import chains
from backend.rag.graph import build_graph, graph_mermaid
from backend.service.chat import pick_players
from backend.settings import get_config
from backend.store import chroma_store
from backend.tests.conftest import BowEmbeddings, ScriptedLLM

CPLL_ITEM = {"id": "ssw-1987", "title": "Corner Permutation of the Last Layer", "level": "심화"}


def test_cited_numbers():
    assert chains.cited_numbers("A [근거 2]. B [근거 1, 3][근거 2] C [근거4]") == [2, 1, 3, 4]
    assert chains.cited_numbers("인용 없음") == []


def test_format_history_keeps_recent_turns():
    h = [{"role": "user", "content": f"q{i}"} if i % 2 == 0 else {"role": "assistant", "content": f"a{i}"}
         for i in range(10)]
    out = chains.format_history(h, 2)
    assert out.splitlines() == ["사용자: q6", "코치: a7", "사용자: q8", "코치: a9"]
    assert chains.format_history([], 3) == "(없음)"


def test_chain_outputs_fall_back_safely():
    assert chains.extract_queries(ScriptedLLM("검색어는 PLL"), role="", rules="", item="", question="", history="") == []
    assert chains.extract_queries(ScriptedLLM('```json\n["PLL", " ", 3]\n```'),
                                  role="", rules="", item="", question="", history="") == ["PLL"]
    cands = [{"pageid": 1, "title": "A", "wordcount": 10, "snippet": ""},
             {"pageid": 2, "title": "B", "wordcount": None, "snippet": ""}]
    picked = chains.select_docs(ScriptedLLM('{"pageids": [2, 99, 1, 2]}'), role="", rules="", item="",
                                question="", candidates=cands, max_docs=1)
    assert picked == [2]                                       # 후보에 없는 id 제거, 최대 개수
    out = chains.answer(ScriptedLLM("JSON이 아닌 답"), role="", rules="", evidence="", case_names=[],
                        question="", history="")
    assert out == {"answer": "JSON이 아닌 답", "cases": []}


def test_chunk_records_attach_algs_of_chunk_range(cpll_parse):
    page = page_from_parse(cpll_parse, lambda t: "u")
    ids, texts, metas = docs.chunk_records(page, CPLL_ITEM, "CPLL")
    assert ids[0] == "ssw-1987:1987:0" and len(set(ids)) == len(ids)
    assert all(len(t) <= get_config()["chunk"]["size"] + 120 for t in texts)
    all_algs = [a for m in metas for a in json.loads(m["algs"])]
    assert len({(a["case"], a["group"], a["order"]) for a in all_algs}) == 33   # 겹침 구간 중복 제외 33개 전부
    m = metas[1]
    assert m["source_type"] == "speedsolving_wiki" and m["doc_id"] == 1987 and m["item_id"] == "ssw-1987"
    for t, m in zip(texts, metas):
        for case in {a["case"] for a in json.loads(m["algs"])}:
            assert case in t.splitlines()[0]                    # 청크 머리에 케이스 이름


def test_graph_retrieve_and_generate(tmp_chroma, cpll_parse):
    emb = BowEmbeddings()
    meta = chroma_store.get_store("meta", emb)
    docs_store = chroma_store.get_store("docs", emb)
    chroma_store.upsert(meta, ["ssw-1987"], ["제목: Corner Permutation of the Last Layer · 연도: 1981? (불확실)"],
                        [{"item_id": "ssw-1987", "title": CPLL_ITEM["title"], "source_type": "item_meta",
                          "source_url": "u0", "algs_num": None}])
    page = page_from_parse(cpll_parse, lambda t: "u1")
    chroma_store.upsert(docs_store, *docs.chunk_records(page, CPLL_ITEM, "CPLL"))
    chroma_store.upsert(docs_store, ["ssw-58:1:0"], ["Aa Permutation Roux"],
                        [{"item_id": "ssw-58", "doc_title": "다른 항목", "source_type": "speedsolving_wiki"}])

    llm = ScriptedLLM(json.dumps({"answer": "A 퍼뮤테이션 [근거 2]. 연도는 불확실 [근거 1]. [근거 99]",
                                  "case": "aa permutation"}, ensure_ascii=False))
    graph = build_graph(llm, meta, docs_store, role="R", answer_rules="X")
    s = graph.invoke({"item_id": "ssw-1987", "question": "Aa Permutation algorithm", "history": [],
                      "search_queries": ["Aa Permutation"]})

    assert s["evidences"][0]["source_type"] == "item_meta"      # 메타 청크는 검색 없이 항상 1번
    assert all(e["id"].startswith("ssw-1987") for e in s["evidences"])   # item_id 필터
    assert len(s["evidences"]) == 1 + get_config()["retrieve"]["top_k"]
    assert [e["no"] for e in s["citations"]] == [2, 1]          # 없는 번호(99)는 버린다
    assert s["no_citation"] is False
    assert s["cases"] == ["Aa Permutation"]                     # 근거의 표기로 맞춘다 (예전 "case" 형식도 받음)

    player, = pick_players(s["cases"], [], s["citations"], s["evidences"], "심화")
    assert player["case"] == "Aa Permutation" and 1 <= len(player["algs"]) <= 3
    assert set(player["algs"][0]) == {"alg", "stage", "video"} and player["inferred"] is False


def test_graph_rejects_case_not_in_evidence_and_flags_no_citation(tmp_chroma):
    emb = BowEmbeddings()
    meta = chroma_store.get_store("meta", emb)
    docs_store = chroma_store.get_store("docs", emb)
    chroma_store.upsert(meta, ["ssw-454"], ["CFOP method"], [{"title": "CFOP method", "source_type": "item_meta"}])
    llm = ScriptedLLM(json.dumps({"answer": "문서에서 확인되지 않는다.", "case": "T Permutation"}, ensure_ascii=False))
    s = build_graph(llm, meta, docs_store, role="R", answer_rules="X").invoke(
        {"item_id": "ssw-454", "question": "큐브 가격?", "history": []})
    assert s["cases"] == [] and s["no_citation"] is True and s["citations"] == []


def test_graph_structure_has_two_nodes():
    m = graph_mermaid()
    assert "retrieve --> generate" in m and "__start__ --> retrieve" in m
