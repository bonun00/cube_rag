"""
항목 한국어 별칭(title_ko) 초안 생성 — LLM 생성 후 사람이 검수한다.

실행: python -m backend.scripts.gen_title_ko          # 아직 없는 항목만 생성 → data/title_ko.json
      python -m backend.scripts.gen_title_ko --apply  # LLM 호출 없이 title_ko.json을 items.json에 반영만

검수 방법: data/title_ko.json 에서 이름을 고치고 "reviewed": true 로 바꾼 뒤 --apply.
           reviewed=true 이면 출처 기록이 "LLM 생성 후 검수", 아니면 "LLM 생성 (검수 전)"이 된다.
           이미 있는 항목은 다시 생성하지 않으므로 검수한 값이 덮어써지지 않는다.
"""
import argparse
import json
import logging

from backend.domain.items import load_items
from backend.llm import get_chat_model, parse_json
from backend.scripts import collect_items
from backend.settings import path

log = logging.getLogger(__name__)
BATCH = 25

PROMPT = """너는 한국 스피드큐빙 커뮤니티에 익숙한 번역가다.
아래 3x3x3 루빅스 큐브 해법·단계 문서 제목마다 한국 큐버가 부를 법한 짧은 한국어 별칭을 붙여라.

규칙:
- 사람 이름에서 온 해법은 한글 음차 + "해법" (예: Roux method → 루 해법, Petrus Method → 페트루스 해법)
- 널리 쓰는 약어는 약어를 살리고 뜻을 괄호로 짧게 (예: Corner Permutation of the Last Layer → CPLL (윗면 꼭짓점 위치 맞추기))
- 뜻을 모르겠으면 음차만 한다. 지어내지 않는다
- 출력은 JSON 객체만: {{"<id>": "<한국어 별칭>", ...}}

항목 (id | 제목 | 다른 이름):
{rows}"""


def title_ko_path():
    return path("items").parent / "title_ko.json"


def generate(todo: list[dict]) -> dict:
    llm = get_chat_model()
    result = {}
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        rows = "\n".join(
            f"{x['id']} | {x['title']} | {x['infobox'].get('anames', '').replace(chr(10), ', ')}" for x in batch
        )
        out = parse_json(llm.invoke(PROMPT.format(rows=rows)).content)
        for x in batch:
            if out.get(x["id"]):
                result[x["id"]] = {"title": x["title"], "title_ko": out[x["id"]].strip(), "reviewed": False}
        log.info("생성 %d/%d", min(i + BATCH, len(todo)), len(todo))
    return result


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="LLM 호출 없이 items.json에 반영만")
    args = parser.parse_args()

    f = title_ko_path()
    names = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    if not args.apply:
        todo = [x for x in load_items() if x["id"] not in names]
        print(f"생성 대상 {len(todo)}건 (이미 있는 {len(names)}건은 건너뜀)")
        if todo:
            names.update(generate(todo))
            f.write_text(json.dumps(dict(sorted(names.items())), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"저장 → {f}  (검수 후 reviewed: true 로 바꾸고 --apply)")

    items, _ = collect_items.save()
    reviewed = sum(1 for v in names.values() if v.get("reviewed"))
    print(f"items.json 반영: title_ko {sum(1 for x in items if x['title_ko'])}/{len(items)}건, 검수 완료 {reviewed}건")


if __name__ == "__main__":
    main()
