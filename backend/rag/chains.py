"""
프롬프트 실행 + 출력 파싱. LLM이 형식을 어기면 안전한 기본값으로 떨어진다 (원문은 서버 로그에만).
"""
import json
import logging
import re

from backend.llm import parse_json
from backend.rag.prompts import ANSWER_PROMPT, FILTER_PROMPT, PICK_PROMPT, QUERY_PROMPT, SELECT_PROMPT

log = logging.getLogger(__name__)

_CITE = re.compile(r"\[근거\s*([\d,\s]+)\]")


def format_history(history: list[dict] | None, turns: int) -> str:
    """[{role: user|assistant, content}] 중 최근 turns턴(질문+답변)만."""
    if not history:
        return "(없음)"
    recent = history[-turns * 2:] if turns > 0 else []
    names = {"user": "사용자", "assistant": "코치"}
    lines = [f"{names.get(m.get('role'), m.get('role'))}: {m.get('content', '')}" for m in recent]
    return "\n".join(lines) or "(없음)"


def extract_queries(llm, *, role: str, rules: str, item: str, question: str, history: str) -> list[str]:
    out = llm.invoke(QUERY_PROMPT.format_messages(role=role, rules=rules, item=item, question=question, history=history))
    try:
        data = parse_json(out.content)
        return [q.strip() for q in data if isinstance(q, str) and q.strip()]
    except (ValueError, TypeError):
        log.warning("검색어 추출 출력 파싱 실패: %r", out.content[:300])
        return []


def select_docs(llm, *, role: str, rules: str, item: str, question: str,
                candidates: list[dict], max_docs: int) -> list[int]:
    if not candidates:
        return []
    rows = "\n".join(
        f"{c['pageid']} | {c['title']} | {c['wordcount'] if c['wordcount'] is not None else 'null'} | {c['snippet'][:200]}"
        for c in candidates
    )
    out = llm.invoke(SELECT_PROMPT.format_messages(
        role=role, rules=rules, item=item, question=question, candidates=rows, max_docs=max_docs))
    valid = {c["pageid"] for c in candidates}
    try:
        ids = parse_json(out.content).get("pageids", [])
        picked = [int(i) for i in ids if int(i) in valid]
        return list(dict.fromkeys(picked))[:max_docs]
    except (ValueError, TypeError, AttributeError):
        log.warning("후보 선별 출력 파싱 실패: %r", out.content[:300])
        return []


def answer(llm, *, role: str, rules: str, evidence: str, case_names: list[str],
           question: str, history: str, asked_cases: list[str] | None = None) -> dict:
    """{"answer": str, "cases": [str]} — 예전 형식 "case": str 도 받는다."""
    as_list = lambda xs: json.dumps(xs, ensure_ascii=False) if xs else "(없음)"  # noqa: E731
    out = llm.invoke(ANSWER_PROMPT.format_messages(
        role=role, rules=rules, evidence=evidence, question=question, history=history,
        case_names=as_list(case_names), asked_cases=as_list(asked_cases or [])))
    try:
        data = parse_json(out.content)
        text = str(data.get("answer") or "").strip()
        raw = data.get("cases", data.get("case"))
        raw = raw if isinstance(raw, list) else [raw]
        cases = [c.strip() for c in raw if isinstance(c, str) and c.strip()]
        return {"answer": text, "cases": list(dict.fromkeys(cases))}
    except (ValueError, TypeError, AttributeError):
        log.warning("답변 출력 JSON 파싱 실패 — 원문을 답변으로 사용")
        return {"answer": out.content.strip(), "cases": []}


def parse_condition(llm, *, role: str, rules: str, condition: str) -> dict:
    """{"query": str, "filters": {이름: 값}} — 값이 null인 필터는 뺀다. 실패하면 조건 원문으로 검색."""
    out = llm.invoke(FILTER_PROMPT.format_messages(role=role, rules=rules, condition=condition))
    try:
        data = parse_json(out.content)
        filters = {k: v for k, v in (data.get("filters") or {}).items() if v is not None}
        return {"query": str(data.get("query") or condition), "filters": filters}
    except (ValueError, TypeError, AttributeError):
        log.warning("조건 파싱 출력 실패: %r", out.content[:300])
        return {"query": condition, "filters": {}}


def pick_items(llm, *, role: str, condition: str, candidates: list[tuple[str, str]]) -> list[dict]:
    """[{"id", "reason"}] — 후보에 있는 id만, 중복 없이."""
    if not candidates:
        return []
    rows = "\n".join(f"{cid} | {desc}" for cid, desc in candidates)
    out = llm.invoke(PICK_PROMPT.format_messages(role=role, condition=condition, candidates=rows))
    valid = {cid for cid, _ in candidates}
    try:
        picked, seen = [], set()
        for x in parse_json(out.content).get("items", []):
            cid = str(x.get("id", ""))
            if cid in valid and cid not in seen:
                seen.add(cid)
                picked.append({"id": cid, "reason": str(x.get("reason") or "").strip()})
        return picked
    except (ValueError, TypeError, AttributeError):
        log.warning("항목 선별 출력 파싱 실패: %r", out.content[:300])
        return []


def cited_numbers(text: str) -> list[int]:
    """본문의 [근거 N] / [근거 1, 3] 번호 (등장 순서, 중복 없음)."""
    nums = []
    for m in _CITE.finditer(text):
        nums += [int(n) for n in re.findall(r"\d+", m.group(1))]
    return list(dict.fromkeys(nums))
