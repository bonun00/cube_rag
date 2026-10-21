"""
LangGraph — retrieve → generate 두 노드.

retrieve: 선택 항목 메타 청크(검색 없이 항상) + 고정 청크(pinned_ids, 서비스가 정함)
          + 외부 문서 컬렉션에서 item_id 필터 Top-k (MMR 옵션) → 병합·중복 제거 → 근거 번호 부여
generate: 근거만으로 답변(JSON) → 본문의 [근거 N]을 파싱해 실제 인용된 근거만 반환, 인용 0개면 no_citation
          cases는 근거의 algs에 실제로 나온 케이스 이름만 남긴다

문서 수집(검색어 추출·검색·선별·색인)은 그래프 앞에서 서비스 계층이 한다.
"""
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.rag import chains
from backend.settings import get_config
from backend.store import chroma_store


class RagState(TypedDict, total=False):
    item_id: str
    question: str
    history: list[dict]
    search_queries: list[str]      # 서비스가 만든 검색어 — 검색 질의를 보강한다 (한국어 질문 ↔ 영어 문서)
    use_mmr: bool | None           # None이면 config.yaml 값
    pinned_ids: list[str]          # 임베딩 순위와 상관없이 근거에 넣을 청크 (예: 질문에 이름이 나온 케이스)
    asked_cases: list[str]         # 질문에 언급된 케이스 — 답변 프롬프트에 알려 준다
    evidences: list[dict]          # {no, id, title, source_type, url, text, algs}
    answer: str
    cases: list[str]
    citations: list[dict]          # 실제 인용된 근거 (evidences 원소)
    no_citation: bool


def _evidence(doc, no: int) -> dict:
    m = doc.metadata
    return {
        "no": no,
        "id": doc.id,
        "title": m.get("doc_title") or m.get("title") or "",
        "source_type": m.get("source_type", ""),
        "url": m.get("source_url", ""),
        "text": doc.page_content,
        "algs": json.loads(m["algs"]) if m.get("algs") else [],
    }


def _norm(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


def format_evidence(evidences: list[dict]) -> str:
    if not evidences:
        return "(근거 없음)"
    return "\n\n".join(f"[근거 {e['no']}] {e['title']} ({e['source_type']})\n{e['text']}" for e in evidences)


def build_graph(llm, meta_store, docs_store, *, role: str, answer_rules: str):
    cfg = get_config()

    def retrieve(state: RagState) -> RagState:
        rcfg = cfg["retrieve"]
        docs = chroma_store.get_by_ids(meta_store, [state["item_id"]])
        if state.get("pinned_ids"):
            docs += chroma_store.get_by_ids(docs_store, state["pinned_ids"])
        query = " ".join([state["question"], *state.get("search_queries", [])])
        use_mmr = state.get("use_mmr")
        docs += chroma_store.search(
            docs_store, query, k=rcfg["top_k"], where={"item_id": state["item_id"]},
            mmr=rcfg["use_mmr"] if use_mmr is None else use_mmr,
            fetch_k=rcfg["mmr_fetch_k"], lambda_mult=rcfg["mmr_lambda"],
        )
        seen, evidences = set(), []
        for d in docs:
            key = d.id or d.page_content
            if key in seen:
                continue
            seen.add(key)
            evidences.append(_evidence(d, len(evidences) + 1))
        return {"evidences": evidences}

    def generate(state: RagState) -> RagState:
        evidences = state["evidences"]
        case_names = list(dict.fromkeys(a["case"] for e in evidences for a in e["algs"] if a.get("case")))
        out = chains.answer(
            llm, role=role, rules=answer_rules, evidence=format_evidence(evidences),
            case_names=case_names, question=state["question"],
            history=chains.format_history(state.get("history"), cfg["chat"]["history_turns"]),
            asked_cases=state.get("asked_cases", []),
        )
        by_no = {e["no"]: e for e in evidences}
        citations = [by_no[n] for n in chains.cited_numbers(out["answer"]) if n in by_no]
        allowed = {_norm(c): c for c in case_names}
        cases = list(dict.fromkeys(allowed[_norm(c)] for c in out["cases"] if _norm(c) in allowed))
        return {"answer": out["answer"], "cases": cases, "citations": citations, "no_citation": not citations}

    g = StateGraph(RagState)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


def graph_mermaid() -> str:
    """그래프 구조 (Mermaid). 노드를 실행하지 않으므로 LLM·DB 없이 출력된다."""
    return build_graph(None, None, None, role="", answer_rules="").get_graph().draw_mermaid()
