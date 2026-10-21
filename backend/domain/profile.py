"""
도메인 문구 — rag/ 프롬프트 틀에 채워 넣는 큐브 전용 역할·규칙. rag/는 이 내용을 모른 채 받아서 쓴다.
"""
from backend.domain.items import LEVEL_ADVANCED, LEVEL_BEGINNER, item_text

ROLE = "너는 입문자부터 숙련자까지 가르치는 스피드큐빙 코치다."

QUERY_RULES = """검색 대상은 영어로 된 Speedsolving.com Wiki다.
- 이 위키 검색은 모든 단어가 들어간 문서만 찾는다. 검색어는 1~3단어 영어 키워드로 짧게 쓴다
- 해법·단계 이름(CFOP, Roux, PLL, OLL, F2L …), 케이스 이름(A Permutation, T Permutation …), 용어(notation, inspection …)를 쓴다
- 한국어 질문이면 위키에서 쓰는 영어 용어로 바꾼다 (꼭짓점 = corner, 모서리 = edge, 윗면 = last layer, 공식 = algorithm)
- 최대 {max_queries}개, 질문에 꼭 필요한 것만"""

SELECT_RULES = """- 질문에 답하는 데 직접 도움이 되는 문서만 고른다. 다른 퍼즐(Megaminx, 4x4x4 등) 문서는 질문이 그 퍼즐을 묻지 않으면 고르지 않는다
- 제목·요약만 보고 판단한다. wordcount가 null이면 리다이렉트로 들어온 문서라 길이를 모르는 것이다"""

ANSWER_RULES = """- 쉬운 한국어로 설명한다. 큐브 전문 용어는 처음 나올 때 괄호로 짧게 풀이한다 (예: PLL(윗면 조각 위치 맞추기))
- 공식은 근거에 적힌 그대로 쓴다. 근거에 없는 공식을 지어내지 않는다
- 연도·제안자 등에 '?'가 붙어 있거나 (불확실)로 표시돼 있으면 확실하지 않다고 함께 알려 준다
- 질문에 언급된 케이스가 있으면 그 케이스의 공식을 근거에서 찾아 안내한다
- cases: 답변에서 공식을 안내한 케이스들을 아래 '근거에 나온 케이스 이름' 표기 그대로 쓴다. 없으면 빈 배열"""


FILTER_RULES = """- query: 해법 특징을 담은 짧은 영어 문장 (예: "beginner friendly method with few algorithms", "fewest moves method")
- filters.level: 사용자가 처음·초보·입문용을 원하면 "입문", 고급·숙련자용이면 "심화", 말하지 않았으면 null
- filters.algs_max / filters.algs_min: 외울 공식 수 조건이 숫자로 있을 때만 정수 (예: "공식 20개 이하" → algs_max 20). "공식 적은"처럼 숫자가 없으면 null
- filters.moves_max: 평균 이동 수 조건이 숫자로 있을 때만 정수, 없으면 null"""

# 조건 탐색 필터 이름 → (메타데이터 키, 연산자)
FILTER_FIELDS = {
    "level": ("level", "$eq"),
    "algs_max": ("algs_num", "$lte"),
    "algs_min": ("algs_num", "$gte"),
    "moves_max": ("moves_num", "$lte"),
}
FILTER_VALUES = {"level": {LEVEL_BEGINNER, LEVEL_ADVANCED}}


def item_card(item: dict) -> dict:
    """조건 탐색 카드에 들어가는 항목 정보."""
    info = item["infobox"]
    return {
        "id": item["id"], "title": item["title"], "title_ko": item.get("title_ko") or "",
        "level": item["level"], "algs": info.get("algs"), "moves": info.get("moves"),
    }


def describe_item(item: dict) -> str:
    """프롬프트에 넣는 선택 항목 설명 (색인 텍스트와 같은 형식)."""
    return f"{item_text(item)} · 레벨: {item['level']}"
