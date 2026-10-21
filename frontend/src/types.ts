// 백엔드 backend/api/schemas.py 와 같은 모양

export type Level = "입문" | "심화";

export interface Item {
  id: string;
  title: string;
  title_ko: string;
  level: Level;
  aliases: string[];
  proposers: string[];
  year: string | null;
  year_uncertain: boolean;
  steps: string | null;
  algs: string | null;
  algs_num: number | null;
  moves: string | null;
  purpose: string[];
  summary: string;
  url: string;
}

export interface Status {
  counts: Record<string, number>;
  items: number;
  api_key_set: boolean;
  missing_env: string[];
}

export interface Citation {
  no: number;
  title: string;
  source_type: string;
  url: string;
}

export interface PlayerAlg {
  alg: string;
  stage: string | null;
  video: string | null;
}

export interface Player {
  case: string;
  algs: PlayerAlg[];
  /** 답변이 직접 안내하지 않았지만 질문에 나온 케이스라 위키 공식 목록에서 띄운 카드 */
  inferred?: boolean;
}

export interface ChatResult {
  answer: string;
  citations: Citation[];
  players?: Player[];
  /** 예전 형식 (localStorage에 남은 대화) */
  player?: Player | null;
  no_citation: boolean;
  notes: string[];
}

export type Stage = "queries" | "collect" | "generate";

export interface Progress {
  stage: Stage;
  message: string;
  count: number | null;
}

export interface SearchCard {
  id: string;
  title: string;
  title_ko: string;
  level: Level;
  algs: string | null;
  moves: string | null;
  reason: string;
}

export interface SearchResult {
  cards: SearchCard[];
  filters: Record<string, unknown>;
  notes: string[];
}

export type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; result?: ChatResult; error?: string };
