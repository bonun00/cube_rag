"""
질문에서 케이스 이름 찾기 — "Z 퍼뮤테이션", "z perm", "Z-PLL", "T랑 Y 퍼뮤테이션" → Permutation 케이스 이름.

임베딩은 PLL 21개 케이스처럼 생김새가 같은 청크를 케이스 이름 한 글자로 구별하지 못한다
(실측: "Z 퍼뮤테이션 공식" 질문에서 Z 청크가 31개 중 6·17위 → Top-4 밖).
그래서 이 해법에 색인된 문서에 실제로 있는 케이스 이름만 후보로 두고, 질문 속 표기를 직접 맞춘다.
"""
import re

_PERMUTATION = re.compile(r"^([A-Za-z]{1,2})\s+permutation$", re.I)
_SUFFIX = r"(?:permutation|perm|퍼뮤테이션|퍼뮤|펌|pll)"
_JOIN = r"(?:,|/|&|\band\b|\bor\b|이랑|랑|하고|와|과|및)"
# "t perm", "t랑 y 퍼뮤테이션", "na, nb perm" — 이름(1~2글자) 목록 + 접미사 하나
_LIST = re.compile(
    rf"(?<![a-z0-9])((?:[a-z]{{1,2}}\s*{_JOIN}\s*)*[a-z]{{1,2}})\s?{_SUFFIX}(?![a-z])"
)
_JOIN_RE = re.compile(_JOIN)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


def find_cases(text: str, case_names: list[str], limit: int) -> list[str]:
    """text에 언급된 케이스 이름 (나온 순서, 최대 limit개). case_names 밖의 이름은 돌려주지 않는다.

    - 케이스 이름 전체 ("Bowtie Cases", "Z Permutation")
    - Permutation 케이스는 짧은 표기도: "z perm", "z퍼뮤테이션", "z pll", "t랑 y 퍼뮤테이션"
    - a/b 짝(Aa·Ab, Ua·Ub …)은 "a 퍼뮤테이션"처럼 a/b 없이 물으면 둘 다
    """
    t = f" {_norm(text)} "
    hits: dict[str, int] = {}

    for case in case_names:                          # 1) 이름 전체
        m = re.search(rf"(?<![a-z0-9]){re.escape(_norm(case))}(?![a-z0-9])", t)
        if m:
            hits[case] = m.start()

    stems, families = {}, {}
    for case in case_names:
        m = _PERMUTATION.match(case.strip())
        if not m:
            continue
        stem = m.group(1).lower()
        stems[stem] = case
        if re.fullmatch(r"[a-z][ab]", stem):
            families.setdefault(stem[0], []).append(case)

    for m in _LIST.finditer(t):                      # 2) 짧은 표기 목록
        names = _JOIN_RE.sub(lambda j: " " * len(j.group()), m.group(1))
        for tok in re.finditer(r"[a-z]{1,2}", names):
            pos = m.start(1) + tok.start()
            s = tok.group()
            if s in stems:
                hits.setdefault(stems[s], pos)
            elif s in families and not any(c in hits for c in families[s]):
                for c in families[s]:
                    hits.setdefault(c, pos)

    ordered = sorted(hits, key=lambda c: (hits[c], case_names.index(c)))
    return ordered[:limit]
