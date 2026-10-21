# 남은 작업

2026-10-21 기준. 1~6단계와 케이스 공식 검색 수정은 끝났고, 7·8단계와 아래 미해결 항목이 남아 있다.

## 단계 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 프로젝트 뼈대, requirements, config.yaml, .env.example, README 초안 | 완료 |
| 2 | 항목 수집(`collect_items.py`), `title_ko` 생성 스크립트, `cube_meta` 색인 | 완료 (`title_ko`는 아직 생성·검수 안 함) |
| 3 | 위키 수집 모듈: 검색, snippet 정제, 본문, 공식 추출(CPLL 33개), 캐시 | 완료 |
| 4 | `cube_docs` 색인, 프롬프트 3개, LangGraph, CLI | 완료 (실제 GMS로 일부 질문 확인) |
| 5 | FastAPI 엔드포인트 + SSE, 조건 탐색 | 완료 |
| 6 | React 화면 | 완료 (실제 GMS로 PLL 케이스 질문 확인) |
| 7 | MMR 토글, 설정값 변경 비교 스크립트 | **미완료** |
| 8 | RAG 전후 비교 스크립트 | **미완료** |

입문 로드맵은 범위에서 뺐다 (코드·문서 모두 삭제). 특화 기능(F2010)은 공식 3D 재생만 남는다.

## 집에서 이어서 하기 (새 PC 준비)

저장소에 올라가지 않는 것: `.env`, `.venv/`, `frontend/node_modules/`, `data/cache/`(수집 캐시), `data/chroma/`(Vector DB).
그래서 새 PC에서는 아래를 한 번 해야 한다. 명령은 모두 `cube_rag/` 폴더에서.

1. Python 3.12 가상환경 + 패키지

   ```bash
   python -m venv .venv
   ```

   ```bash
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. 프론트 패키지 (Node 20 이상)

   ```bash
   cd frontend
   npm install
   ```

3. `.env` 만들기: `copy .env.example .env` 후 `GMS_KEY`, `GMS_BASE_URL`, `CHAT_MODEL`, `EMBED_MODEL`, `WIKI_USER_AGENT` 채우기
   - 학교에서 쓴 값: `GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1`, `CHAT_MODEL=gpt-4.1`, `EMBED_MODEL=text-embedding-3-small`
4. 항목 색인 (Vector DB가 비어 있으므로 필수)

   ```bash
   .venv\Scripts\python.exe -m backend.scripts.index_items
   ```

5. 외부 문서는 질문할 때 다시 수집된다 (수집 캐시가 없어서 첫 질문마다 위키를 다시 부른다)
6. 서버: 백엔드 `.venv\Scripts\python.exe -m uvicorn backend.api.main:app --reload`, 화면 `cd frontend` → `npm run dev` → http://localhost:5173
   - 백엔드는 꼭 `cube_rag\.venv`의 python으로 띄운다 (학교 PC에서는 바깥 실습 폴더 `.venv`로 띄워져 있었다)
7. 테스트: `.venv\Scripts\python.exe -m pytest` (42개, 네트워크·키 없이 돈다)

## 미해결 문제

- [ ] **답변이 `[근거 N]`을 안 붙이는 경우가 있다**
  - "T랑 Y 퍼뮤테이션 공식 알려줘"(PLL): CLI에서는 인용했지만, 화면에서 다시 물었을 때는 인용 0개 → "근거 문서를 인용하지 않았습니다" 경고. 공식 카드는 정상으로 나옴
  - 수정 후보: 답변 프롬프트의 인용 규칙 강화, 또는 인용이 0개면 한 번 다시 생성
- [ ] **케이스 공식 검색 단위 테스트 추가**: PLL 저장본(`backend/tests/fixtures/parse_pll.json`)으로
  - `domain/cases.py`의 `find_cases` — "Z 퍼뮤테이션", "z perm", "T랑 Y 퍼뮤테이션", "A 퍼뮤테이션"(Aa·Ab) 등
  - `domain/docs.py`의 케이스 단위 청킹 — 한 청크에 케이스 하나, 공식 326개 전부 포함
  - 질문에서 찾은 케이스 청크가 근거에 고정되고 `players`가 나오는지
  - 대표 질문(`data/eval_questions.json`)에 PLL 케이스 질문 추가
- [ ] 바깥 폴더 `streamlit_lab/.env.example`에 실제 GMS 키가 그대로 있다 → 값 지우기 (공유한 적 있으면 키 재발급). 이 저장소에는 포함되지 않는다

## 7단계 — 미완료

- [ ] **MMR 토글**: 화면에 MMR 켬/끔 스위치 추가 → `/api/chat`의 `use_mmr`로 전달
  - 백엔드는 이미 준비돼 있다 (`ChatRequest.use_mmr`, CLI `--mmr` / `--no-mmr`)
- [ ] **설정값 변경 비교 스크립트**: 청크 크기·중복, Top-k, MMR 켬/끔을 바꿔 가며 대표 질문 5개(`data/eval_questions.json`)를 실행
  - 비교 항목: 근거로 뽑힌 문서, 인용 수, `no_citation` 여부, 답변 내용
  - 결과를 markdown 표로 저장
  - 청크 설정을 바꾸면 `cube_docs`를 다시 색인해야 하므로, 설정별로 별도 Chroma 폴더를 쓰는 방식이 필요하다

## 8단계 — 미완료

- [ ] **RAG 전후 비교 스크립트**: 대표 질문 5개를 RAG 없이(LLM만)와 RAG 있음으로 각각 답하게 해서 나란히 markdown으로 저장

## 아직 안 해 본 것 (실제 GMS로)

- [ ] `title_ko` 생성 → `data/title_ko.json` 검수(`"reviewed": true`) → `gen_title_ko --apply` → `index_items` 다시 실행
- [ ] `ask --eval`로 대표 질문 5개 전부 확인
  - 1번(CPLL "꼭짓점 3개"): Aa/Ab 공식 카드가 나오는지
  - 2번: 제안자 Jessica Fridrich, 연도 1981?을 불확실하다고 표시하는지
  - 3번: 2GR 공식 84개
  - 4번: Roux vs CFOP 공식 수 비교
  - 5번(큐브 가격): "문서에서 확인되지 않는다"로 답하는지
- [ ] 조건 탐색을 실제 LLM으로 확인 ("공식 적은 입문 해법" 등)
- [ ] 공식 선택 우선순위: 영상 우선 규칙 때문에 입문자에게도 회전(x)이 들어간 공식이 뽑힐 수 있다 — 원하는 동작인지 판단

## 받으면 반영할 것

- [ ] 큐토리얼 7단계 해법 문서 → `cube_docs`에 `source_type="cubetorial"`로 색인
- [ ] 큐토리얼 3D 큐브 코드 → `frontend/src/components/cube/CubePlayer.tsx`의 export 한 줄 교체

## 완료한 수정 기록

**케이스 공식 검색 문제** — PLL 선택 후 "Z 퍼뮤테이션 공식 보여줘" → "문서에서 확인되지 않는다". 임베딩이 PLL 케이스 청크를 구별하지 못해 Z 청크가 Top-4 밖(6·17위)이었다.

- [x] 질문에서 케이스 이름 인식 → 그 케이스 청크를 근거에 고정 (`domain/cases.py`, `service/chat.py`)
- [x] 3D 카드 보장: 답변이 케이스를 빠뜨려도 질문에서 찾은 케이스로 카드를 띄움 (`inferred` 표시)
- [x] 여러 케이스: `players` 배열, 화면은 케이스 탭 (최대 3개, `alg_picker.max_cases`)
- [x] 케이스(h2) 단위 청킹 + 재색인 (`reindex_docs.py`)
- 확인: Z(공식 3개, 위키에 영상 없음), T·Y(탭 2개, 영상 링크 있음) 모두 3D 카드가 나옴
