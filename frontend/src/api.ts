import type { ChatMessage, ChatResult, Item, Progress, SearchResult, Status } from "./types";

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

const NETWORK_MESSAGE = "서버에 연결하지 못했습니다. 백엔드(uvicorn)가 켜져 있는지 확인해 주세요.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("network", NETWORK_MESSAGE);
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const d = body?.detail;
    if (d && typeof d === "object" && d.message) return new ApiError(d.code ?? "error", d.message);
  } catch {
    /* 본문이 JSON이 아니면 아래 기본 문구 */
  }
  return new ApiError("error", `요청을 처리하지 못했습니다 (${res.status})`);
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getStatus = () => request<Status>("/api/status");
export const getItems = () => request<Item[]>("/api/items");
export const searchItems = (condition: string) => request<SearchResult>("/api/items/search", json({ condition }));

/** 서버로 보낼 대화 기록 — 서버가 다시 최근 N턴으로 자른다 */
function toHistory(messages: ChatMessage[]) {
  return messages
    .filter((m) => m.role === "user" || !("error" in m && m.error))
    .slice(-12)
    .map((m) => ({ role: m.role, content: m.content }));
}

/**
 * POST /api/chat SSE 읽기. EventSource는 GET만 되므로 fetch 스트림을 직접 파싱한다.
 * progress 이벤트마다 onProgress, result가 오면 반환, error가 오면 ApiError.
 */
export async function streamChat(
  itemId: string,
  question: string,
  history: ChatMessage[],
  onProgress: (p: Progress) => void,
  options: { useMmr?: boolean | null; signal?: AbortSignal } = {},
): Promise<ChatResult> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      ...json({ item_id: itemId, question, history: toHistory(history), use_mmr: options.useMmr ?? null }),
      signal: options.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("network", NETWORK_MESSAGE);
  }
  if (!res.ok || !res.body) throw await toApiError(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const ev = parseEvent(block);
      if (!ev) continue;
      if (ev.event === "progress") onProgress(ev.data as Progress);
      else if (ev.event === "result") return ev.data as ChatResult;
      else if (ev.event === "error") {
        const d = ev.data as { code: string; message: string };
        throw new ApiError(d.code, d.message);
      }
    }
  }
  throw new ApiError("server_error", "답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요.");
}

function parseEvent(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith(":")) continue; // keep-alive ping
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}
