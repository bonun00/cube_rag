# 큐브 RAG — 루빅스 큐브 해법 도메인 지식 서비스

SSAFY AI 코어 프로젝트 2회차 "RAG 기반 도메인 지식 서비스".
왼쪽에서 3x3x3 큐브 해법(항목)을 고르고 질문하면, Speedsolving.com Wiki 문서를 근거로 달아 쉬운 한국어로 답한다.

> 초안 — 단계별로 채워 나간다.

## 주요 기능

| 기능 | 내용 |
|---|---|
| 항목 선택 · 대화 | 해법을 고르면 항목별로 대화 기록을 따로 유지 |
| 근거 기반 답변 | 질문할 때마다 위키를 검색·선별·수집해 색인 → 근거 번호 `[근거 N]`를 달아 답변. 근거가 없으면 없다고 답함 |
| 공식 3D 재생 | 근거에 공식이 있으면 위키 순서·시연 영상 유무 기준으로 골라 3D 재생 + 시연 영상 링크 |
| 조건 탐색 | "공식 적은 입문 해법" 같은 자연어 조건으로 항목 카드 추천 |
| 진행 상태 | 검색어 추출 → 문서 수집 → 답변 생성 단계를 SSE로 표시 |

## 폴더 구조

```
backend/
  domain/     큐브 전용 코드 (항목 로드·텍스트, 위키 수집기, 공식 추출·선택)
  store/      Chroma 컬렉션 생성·색인·조회
  rag/        프롬프트 3개, LangGraph 노드·그래프
  service/    질문 처리(수집 → 그래프 → 공식 선택), 조건 탐색
  api/        FastAPI 라우터, 요청/응답 스키마
  scripts/    collect_items.py, index_items.py
  tests/      단위 테스트 (fixtures/ 에 위키 응답 저장본)
  config.yaml 청크 크기·중복·Top-k·MMR·호출 간격 등
  settings.py config.yaml + .env 로더
data/
  items.json  항목 메타데이터
  cache/      수집 캐시 (커밋 안 함)
  chroma/     Vector DB (커밋 안 함)
frontend/     React + TypeScript + Vite
```

도메인에 묶인 코드는 `backend/domain/`에만 둔다. 나머지 모듈은 도메인을 몰라도 동작한다.

## 실행 방법

명령은 모두 프로젝트 루트(`cube_rag/`)에서 실행한다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # 값 채우기
```

| 환경변수 | 설명 |
|---|---|
| `GMS_KEY` | SSAFY GMS API 키 |
| `GMS_BASE_URL` | GMS OpenAI 호환 엔드포인트 |
| `CHAT_MODEL` | 답변·검색어 추출용 모델 이름 |
| `EMBED_MODEL` | 임베딩 모델 이름 |
| `WIKI_USER_AGENT` | 위키 호출 User-Agent (프로젝트명 + 연락처, 영문) |

항목 준비:

```bash
python -m backend.scripts.collect_items             # 항목 수집 → data/items.json (원본은 data/cache에 캐시)
python -m backend.scripts.collect_items --refresh   # 캐시 무시하고 위키에서 다시 받기
python -m backend.scripts.gen_title_ko              # 한국어 별칭 초안 → data/title_ko.json
python -m backend.scripts.gen_title_ko --apply      # 검수(reviewed: true) 후 items.json에 반영
python -m backend.scripts.index_items               # cube_meta 색인 (재실행해도 건수 불변)
```

테스트 (네트워크 없이 `backend/tests/fixtures/`의 위키 응답 저장본 사용):

```bash
pytest
```

CLI 질문 (end-to-end: 검색어 추출 → 수집·색인 → retrieve → generate):

```bash
python -m backend.scripts.ask --item CPLL "꼭짓점 3개가 돌아가 있으면 어떤 공식 써?"
python -m backend.scripts.ask --eval      # data/eval_questions.json 대표 질문 5개
python -m backend.scripts.ask --graph     # LangGraph 구조 (Mermaid)
```

API 서버 (`.env`를 바꾸면 서버를 다시 시작해야 반영된다):

```bash
uvicorn backend.api.main:app --reload     # http://localhost:8000/api/docs
```

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/api/status` | 컬렉션별 색인 건수, 항목 수, API 키 설정 여부, 비어 있는 환경변수 이름 |
| GET | `/api/items?level=입문` | 항목 목록 |
| POST | `/api/chat` | `{item_id, question, history, use_mmr?}` → SSE |
| POST | `/api/items/search` | `{condition}` → `{cards[], filters, notes[]}` |

`/api/chat` SSE 이벤트:
- `progress` `{stage: queries|collect|generate, message, count?}` — 여러 번
- `result` `{answer, citations[{no, title, source_type, url}], players[{case, algs[{alg, stage, video}], inferred}], no_citation, notes[]}`
  - 스펙의 `player`(1개)를 `players`(케이스별, 최대 3개)로 바꿨다. `inferred: true` = 답변이 직접 안내하지 않았지만 질문에 나온 케이스라 위키 공식 목록에서 띄운 카드
- `error` `{code: missing_env|not_found|auth_error|llm_unavailable|server_error, message}` — 화면용 문구만, 원인은 서버 로그

화면 (백엔드를 먼저 띄운 뒤, 다른 터미널에서):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (/api 는 localhost:8000으로 프록시)
```

- 왼쪽: 조건 탐색(카드 클릭 → 그 해법 대화로 이동), 해법 목록(전체·입문·심화 필터, 이름 검색), 색인 건수·API 키 안내
- 가운데: 항목 정보, 항목별 대화(브라우저 localStorage에 항목별로 저장), 진행 단계(검색어 추출 → 문서 수집 → 답변 생성), 답변의 `[근거 N]` 표시, "사용한 근거 N건" 접기, 공식 카드(3D 재생 + 시연 영상 링크)
- 첫 화면 추천 질문 4개, 항목 선택 후 추천 질문 4개
- 3D 큐브: `frontend/src/components/cube/CubePlayer.tsx` 한 줄이 교체 지점 (현재 cubing.js TwistyPlayer, 케이스 상태에서 시작). 재생 전 `(U')` 같은 괄호를 벗긴다 (`(R U R' U')2`처럼 반복 횟수가 붙은 괄호는 유지)

## 데이터 출처와 이용 조건

| 출처 | 사용 범위 | 이용 조건 |
|---|---|---|
| [Speedsolving.com Wiki](https://www.speedsolving.com/wiki/) | 항목 메타데이터(인포박스·요약), 질문 시 수집하는 문서 본문·공식 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — 답변마다 원문 링크로 출처 표시 |
| 큐토리얼 (본인 제작) | 7단계 입문 해법 문서 | 본인 제작물 |
| 항목 한국어 별칭 `title_ko` | 항목 표시·검색 | LLM 생성 후 본인 검수 |

- 위키 API 호출 규칙: User-Agent에 프로젝트명·연락처 포함, 호출 간격 1초, 실패 시 지수 백오프로 최대 3회 재시도
- 같은 검색어는 수집 캐시로 다시 수집하지 않는다
- 이미지(`image` 필드)는 메타데이터에만 두고 색인·화면에 쓰지 않는다

## 항목 데이터

- 수집 범위: `Category:3x3x3_methods`, `Category:3x3x3 last layer substeps` 중 인포박스(Method/Substep Infobox)가 있는 문서 + `Category:3x3x3 beginner methods and substeps` 중 인포박스가 있는 문서
- 리다이렉트는 따라간 뒤의 문서 1건으로 합친다 (예: CPLL → Corner Permutation of the Last Layer). 항목 id = `ssw-<리다이렉트 이후 pageid>`
- `level`: beginner 카테고리 소속이면 `입문`, 아니면 `심화`
- 2026-10-21 수집 기준 172건 (입문 18 · 심화 154)

## 외부 문서 수집 (질문할 때)

- 검색 `list=search`: 모든 단어가 들어간 문서만 나온다(AND). 긴 문장은 0건이므로 1~3단어 영어 키워드로 검색한다
- 검색 결과에 리다이렉트 문서가 섞인다 (예: `CPLL`, `Roux Method`) → 결과 제목을 전부 풀어 리다이렉트 이후 pageid로 중복 제거
- 본문 `action=parse&redirects=1` → 텍스트와 공식(`alg.cubing.net` 링크)을 한 번에 추출. 공식마다 케이스(h2)·그룹(h3)·단계·시연 영상·본문 내 위치를 기록
- 수집 캐시 (`data/cache/`)
  - `collected_queries.json`: (항목ID, 검색어)별 수집 기록 — 같은 항목에서 같은 검색어는 다시 수집하지 않는다
  - `pages/<pageid>.json`, `page_titles.json`: 문서 본문 — 항목이 달라도 같은 문서는 한 번만 받는다 (만료 없음, 지우면 다시 받음)

## RAG 파이프라인

```
질문 ─▶ [서비스] 프롬프트1 검색어 추출 (+ 항목 제목 항상 추가)
        ─▶ 수집 캐시 확인 ─▶ 위키 검색 ─▶ 길이 규칙 ─▶ 프롬프트2 후보 선별 (항목 자체 문서는 항상 포함)
        ─▶ 본문 수집 ─▶ 케이스(h2) 단위 청킹 (청크별 케이스·공식 포함) ─▶ cube_docs 색인
     ─▶ [서비스] 질문에서 케이스 이름 인식 ("Z 퍼뮤테이션", "T랑 Y perm" …) ─▶ 그 케이스 청크를 근거에 고정
     ─▶ [LangGraph] retrieve: 항목 메타 청크(항상) + cube_docs item_id 필터 Top-k (MMR 옵션) ─▶ 근거 번호
                  ─▶ generate: 프롬프트3 {answer, case} ─▶ 실제 인용된 근거만 반환, 인용 0개면 no_citation
     ─▶ [서비스] 답변이 안내한 케이스 + 질문에 나온 케이스마다 alg_picker로 공식 선택 → 공식 카드
```

- 케이스 이름 인식이 필요한 이유: PLL 21개 케이스 청크는 생김새가 거의 같아 임베딩이 "Z" 한 글자를 구별하지 못한다. 실측으로 "Z 퍼뮤테이션 공식" 질문에서 Z 청크가 31개 중 6·17위라 Top-4에 들지 못했다
- 청킹 방식을 바꾼 뒤에는 이미 수집한 문서를 다시 색인한다 (위키 재호출 없음): `python -m backend.scripts.reindex_docs`

- 프롬프트 틀은 `backend/rag/prompts.py`, 큐브 전용 역할·규칙 문구는 `backend/domain/profile.py`
- 대표 질문: `data/eval_questions.json`. 5번은 처음에 "대회 인스펙션 시간 초과 벌점"이었으나 위키 `Inspection` 문서에 +2초 / 17초 초과 DNF가 있어, 위키에 없는 큐브 가격 질문으로 바꿨다 (price·cost·dollar·cheap·budget 검색 0건 확인)

## 알려진 한계

- 제안자는 줄바꿈·쉼표·&·and 기준으로만 나눈다. `"Jessica Fridrich while inventing pll?"`처럼 설명이 붙은 원문은 그대로 한 이름이 된다 (원문은 `proposers_raw`에 보존).
- `algs_num`, `moves_num`은 원문에서 첫 정수만 뽑는다. `"9-42"`처럼 범위로 적힌 값은 최솟값(9)이 되므로 조건 탐색 결과가 원문과 다를 수 있다. 원문 문자열은 그대로 보존한다.

## 진행 상황

- [x] 1. 프로젝트 뼈대, requirements, config.yaml, .env.example, README 초안
- [x] 2. 항목 수집 수정 + cube_meta 색인 (실제 임베딩 색인·title_ko 생성은 GMS 설정 후 실행)
- [x] 3. 위키 수집 모듈 (검색, snippet 정제, 본문, 공식 추출, 캐시) — `pytest` 26개 통과
- [x] 4. cube_docs 색인 + 프롬프트 + LangGraph + CLI (가짜 LLM·임베딩으로 확인, 실제 GMS 실행은 설정 후)
- [x] 5. FastAPI + SSE (+ 조건 탐색 서비스)
- [x] 6. React 화면 (가짜 답변 백엔드로 화면 동작 확인)
- [ ] 7. MMR 토글, 설정값 비교
- [ ] 8. RAG 전후 비교
