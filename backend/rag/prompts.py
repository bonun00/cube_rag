"""
프롬프트. 도메인 문구({role}, {rules})는 호출하는 쪽이 채운다 — 이 모듈은 도메인을 모른다.

RAG 질문 처리 (3개)
1. QUERY_PROMPT  검색어 추출   → JSON 배열
2. SELECT_PROMPT 후보 문서 선별 → {"pageids": [...]}
3. ANSWER_PROMPT 근거 기반 답변 → {"answer": str, "cases": [str]}

조건 탐색 (F2011)
- FILTER_PROMPT 자연어 조건 → 검색 질의 + 메타 필터
- PICK_PROMPT   후보 항목 중 조건에 맞는 것만 + 이유
"""
from langchain_core.prompts import ChatPromptTemplate

QUERY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """{role}
사용자가 고른 항목과 질문을 보고, 답에 필요한 문서를 찾을 검색어를 만든다.

{rules}

출력은 JSON 문자열 배열만 쓴다. 설명·코드 블록 없이. 예: ["PLL", "A Permutation"]"""),
    ("human", """선택 항목: {item}

최근 대화:
{history}

질문: {question}"""),
])

SELECT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """{role}
검색 후보 문서 목록에서 질문에 답하려면 색인해야 할 문서를 고른다.

{rules}
- 최대 {max_docs}개. 쓸 만한 문서가 없으면 빈 배열

출력은 JSON만 쓴다: {{"pageids": [숫자, ...]}}"""),
    ("human", """선택 항목: {item}

질문: {question}

후보 (pageid | 제목 | wordcount | 요약):
{candidates}"""),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """{role}
아래 [근거 N] 내용만 사용해서 질문에 답한다.

규칙:
- 근거에 없는 내용은 추측하지 않는다. 근거로 답할 수 없으면 "문서에서 확인되지 않는다"고 분명히 말한다
- 주요 주장마다 뒤에 출처 번호를 [근거 N] 형식으로 붙인다 (여러 개면 [근거 1][근거 3])
{rules}

근거에 나온 케이스 이름: {case_names}
질문에 언급된 케이스: {asked_cases}

출력은 JSON만 쓴다: {{"answer": "답변 본문", "cases": ["케이스 이름", ...]}}"""),
    ("human", """{evidence}

최근 대화:
{history}

질문: {question}"""),
])

FILTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """{role}
사용자가 말한 조건을 항목 검색 질의와 메타데이터 필터로 바꾼다.

{rules}

출력은 JSON만 쓴다: {{"query": "검색 질의", "filters": {{필터 이름: 값 또는 null}}}}"""),
    ("human", "조건: {condition}"),
])

PICK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """{role}
후보 항목 설명만 보고, 사용자 조건에 맞는 항목만 고른다. 설명에 없는 내용으로 판단하지 않는다.
맞는 항목이 없으면 빈 배열.

출력은 JSON만 쓴다: {{"items": [{{"id": "항목 id", "reason": "조건에 맞는 이유 한 문장 (쉬운 한국어)"}}]}}"""),
    ("human", """조건: {condition}

후보 (id | 설명):
{candidates}"""),
])
