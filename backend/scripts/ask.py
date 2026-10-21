"""
CLI 질문 — 수집 → 색인 → retrieve → generate end-to-end.

실행: python -m backend.scripts.ask --item CPLL "꼭짓점 3개가 돌아가 있으면 어떤 공식 써?"
      python -m backend.scripts.ask --eval        # data/eval_questions.json 대표 질문 전부
      python -m backend.scripts.ask --graph       # LangGraph 구조(Mermaid)만 출력
옵션: --mmr / --no-mmr  (기본은 config.yaml retrieve.use_mmr)
"""
import argparse
import json
import logging
import sys

from backend.domain.items import find_item
from backend.llm import MissingEnvError
from backend.rag.graph import graph_mermaid
from backend.service import chat
from backend.settings import path


def print_progress(stage: str, message: str, data: dict) -> None:
    print(f"  … {message}")


def print_result(r: dict) -> None:
    print("\n[답변]")
    print(r["answer"])
    print(f"\n[사용한 근거 {len(r['citations'])}건]" + ("  ※ 인용 없음 (no_citation)" if r["no_citation"] else ""))
    for c in r["citations"]:
        print(f"  [근거 {c['no']}] {c['title']} · {c['source_type']} · {c['url']}")
    for p in r["players"]:
        print(f"\n[공식 — {p['case']}]" + ("  (질문에서 찾은 케이스 — 위키 공식 목록에서 가져옴)" if p["inferred"] else ""))
        for a in p["algs"]:
            print(f"  {a['alg']}  ({a['stage']})" + (f"  영상: {a['video']}" if a["video"] else ""))
    if r["notes"]:
        print("\n[안내] " + " / ".join(r["notes"]))
    print(f"\n(검색어: {', '.join(r['queries'])} · 새로 색인한 문서: {[d['title'] for d in r['collected']]})")


def run(item_name: str, question: str, history: list[dict], use_mmr: bool | None) -> dict | None:
    item = find_item(item_name)
    if item is None:
        print(f"항목을 찾을 수 없음: {item_name}")
        return None
    print(f"\n=== [{item['title']}] {question}")
    r = chat.ask(item["id"], question, history, progress=print_progress, use_mmr=use_mmr)
    print_result(r)
    return r


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?")
    p.add_argument("--item", help="항목 id · 제목 · 다른 이름 (예: CPLL, 2GR Method)")
    p.add_argument("--eval", action="store_true", help="대표 질문 전부 실행")
    p.add_argument("--graph", action="store_true", help="그래프 구조만 출력")
    p.add_argument("--mmr", dest="mmr", action="store_true", default=None)
    p.add_argument("--no-mmr", dest="mmr", action="store_false")
    args = p.parse_args()

    if args.graph:
        print(graph_mermaid())
        return
    try:
        if args.eval:
            questions = json.loads((path("items").parent / "eval_questions.json").read_text(encoding="utf-8"))
            for q in questions:
                run(q["item_title"], q["question"], [], args.mmr)
                print(f"(기대: {q['expect']})")
        elif args.item and args.question:
            run(args.item, args.question, [], args.mmr)
        else:
            p.print_help()
    except MissingEnvError as e:
        print(f"설정 필요: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
