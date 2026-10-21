"""
보여줄 공식 선택 — LLM이 고르지 않고 규칙으로 고른다.

1. 해당 케이스 + group == "Speedsolving Algorithms"만
2. 시연 영상 있는 공식 우선
3. (입문 레벨만) M/S/E 슬라이스, x/y/z 회전 개수가 적은 공식 우선
4. 위키 등장 순서
5. 입문 1개, 심화 최대 3개 (config.yaml alg_picker)

위키 순서는 동점이 없으므로 3을 4보다 앞에 둬야 입문 규칙이 실제로 효과가 있다.
"""
import re

from backend.domain.alg_extractor import Alg
from backend.domain.items import LEVEL_BEGINNER
from backend.settings import get_config

SPEED_GROUP = "Speedsolving Algorithms"
_SLICE_ROTATION = re.compile(r"[MSExyz]")


def _norm(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "")).strip().lower()


def slice_rotation_count(alg: str) -> int:
    return len(_SLICE_ROTATION.findall(alg))


def case_names(algs: list[Alg]) -> list[str]:
    """공식이 있는 케이스 이름 (등장 순서, 중복 없음) — generate의 case 검증에 쓴다."""
    seen = []
    for a in algs:
        if a.case and a.case not in seen:
            seen.append(a.case)
    return seen


def pick(algs: list[Alg], case: str, level: str) -> list[Alg]:
    cfg = get_config()["alg_picker"]
    beginner = level == LEVEL_BEGINNER
    limit = cfg["beginner_max"] if beginner else cfg["advanced_max"]

    target = _norm(case)
    candidates, seen = [], set()
    for a in algs:
        if _norm(a.case) == target and a.group == SPEED_GROUP and a.alg not in seen:
            seen.add(a.alg)                          # 여러 문서에서 같은 공식이 모이면 한 번만
            candidates.append(a)

    # 등장 순서 = 입력 목록 순서 (여러 문서가 섞이면 문서 순서 → 문서 안 순서로 넘겨준다)
    ranked = sorted(
        enumerate(candidates),
        key=lambda ia: (ia[1].video is None, slice_rotation_count(ia[1].alg) if beginner else 0, ia[0]),
    )
    return [a for _, a in ranked[:limit]]
