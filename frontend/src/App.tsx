import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getItems, getStatus, streamChat } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { Sidebar } from "./components/Sidebar";
import type { ChatMessage, Item, Progress, Status } from "./types";

const STORAGE_KEY = "cube-rag:conversations:v1";

// 항목별 대화 기록은 이 브라우저에만 저장한다 (막혀 있으면 메모리에만)
function loadConversations(): Record<string, ChatMessage[]> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function saveConversations(c: Record<string, ChatMessage[]>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(c));
  } catch {
    /* 저장 실패해도 화면은 그대로 */
  }
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [conversations, setConversations] = useState(loadConversations);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Progress[]>([]);
  const chatRef = useRef<HTMLDivElement>(null);

  const refreshStatus = useCallback(() => {
    getStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    getItems()
      .then(setItems)
      .catch((e) => setItemsError(e instanceof ApiError ? e.message : "해법 목록을 불러오지 못했습니다."));
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => saveConversations(conversations), [conversations]);

  const append = (itemId: string, msg: ChatMessage) =>
    setConversations((c) => ({ ...c, [itemId]: [...(c[itemId] ?? []), msg] }));

  function select(id: string) {
    setSelectedId(id);
    chatRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); // 좁은 화면에서 대화로 이동
  }

  async function ask(itemId: string, question: string) {
    if (pendingId) return;
    const history = conversations[itemId] ?? [];
    append(itemId, { role: "user", content: question });
    setPendingId(itemId);
    setProgress([]);
    try {
      const result = await streamChat(itemId, question, history, (p) => setProgress((ps) => [...ps, p]));
      append(itemId, { role: "assistant", content: result.answer, result });
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "답변 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
      append(itemId, { role: "assistant", content: "", error: message });
    } finally {
      setPendingId(null);
      setProgress([]);
      refreshStatus();
    }
  }

  const item = items.find((i) => i.id === selectedId) ?? null;

  return (
    <div className="layout">
      <Sidebar
        items={items}
        itemsError={itemsError}
        status={status}
        selectedId={selectedId}
        onSelect={select}
      />
      <div ref={chatRef} className="chat-wrap">
        <ChatPanel
          item={item}
          items={items}
          messages={item ? conversations[item.id] ?? [] : []}
          progress={pendingId === selectedId ? progress : []}
          busy={pendingId !== null}
          pendingHere={pendingId !== null && pendingId === selectedId}
          onAsk={(q) => item && ask(item.id, q)}
          onPickStarter={(id, q) => {
            select(id);
            ask(id, q);
          }}
        />
      </div>
    </div>
  );
}
