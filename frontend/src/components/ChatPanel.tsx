import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Item, Progress, Stage } from "../types";
import { AnswerView } from "./AnswerView";

interface Props {
  item: Item | null;
  messages: ChatMessage[];
  progress: Progress[];
  busy: boolean; // 어느 항목이든 답변을 기다리는 중 (한 번에 한 질문)
  pendingHere: boolean; // 지금 보고 있는 항목의 답변을 기다리는 중
  onAsk: (question: string) => void;
  onPickStarter: (itemId: string, question: string) => void;
  items: Item[];
}

// 첫 화면 추천 질문 — 항목을 고르기 전 (항목 제목으로 찾는다)
const STARTERS: { title: string; question: string }[] = [
  { title: "Layer by layer", question: "처음 배우는 사람은 어떤 순서로 풀어?" },
  { title: "CFOP method", question: "CFOP는 어떤 단계로 이루어져 있어?" },
  { title: "Corner Permutation of the Last Layer", question: "꼭짓점 3개가 돌아가 있으면 어떤 공식 써?" },
  { title: "Roux method", question: "CFOP보다 외울 공식이 적어?" },
];

// 항목을 고른 뒤 추천 질문
const ITEM_QUESTIONS = ["이 해법은 어떤 순서로 풀어?", "누가 만들었어?", "외울 공식이 몇 개야?", "입문자도 배울 만해?"];

const STAGES: { stage: Stage; label: string }[] = [
  { stage: "queries", label: "검색어 추출" },
  { stage: "collect", label: "문서 수집" },
  { stage: "generate", label: "답변 생성" },
];

export function ChatPanel({ item, messages, progress, busy, pendingHere, onAsk, onPickStarter, items }: Props) {
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, progress.length, pendingHere]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (!q || busy || !item) return;
    onAsk(q);
    setText("");
  }

  if (!item) {
    const starters = STARTERS.map((s) => ({ ...s, item: items.find((i) => i.title === s.title) })).filter(
      (s) => s.item,
    );
    return (
      <main className="chat">
        <div className="welcome">
          <h2>어떤 해법이 궁금하세요?</h2>
          <p className="muted">
            왼쪽에서 해법을 고르면 위키 문서를 찾아 근거와 함께 답해 드립니다. 공식이 나오면 3D로 돌려 볼 수 있어요.
          </p>
          <div className="starters">
            {starters.map((s) => (
              <button
                key={s.question}
                className="starter"
                disabled={busy}
                onClick={() => onPickStarter(s.item!.id, s.question)}
              >
                <span className="starter-item">{s.item!.title_ko || s.item!.title}</span>
                <span>{s.question}</span>
              </button>
            ))}
          </div>
        </div>
      </main>
    );
  }

  const done = new Set(progress.map((p) => p.stage));
  const last = progress[progress.length - 1];

  return (
    <main className="chat">
      <ItemHeader item={item} />
      <div className="messages">
        {!messages.length && (
          <div className="suggest">
            <p className="muted">이런 걸 물어볼 수 있어요</p>
            <div className="chips">
              {ITEM_QUESTIONS.map((q) => (
                <button key={q} className="chip" onClick={() => onAsk(q)} disabled={busy}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="bubble user">
              {m.content}
            </div>
          ) : (
            <div key={i} className="bubble bot">
              {m.error ? <p className="notice error">{m.error}</p> : <AnswerView result={m.result!} level={item.level} />}
            </div>
          ),
        )}
        {busy && !pendingHere && <p className="muted">다른 해법의 답변을 만드는 중입니다. 끝나면 질문할 수 있어요.</p>}
        {pendingHere && (
          <div className="bubble bot progress" aria-live="polite">
            <ol className="steps">
              {STAGES.map(({ stage, label }) => {
                const current = last?.stage === stage;
                const cls = current ? "step current" : done.has(stage) ? "step done" : "step";
                return (
                  <li key={stage} className={cls}>
                    {label}
                  </li>
                );
              })}
            </ol>
            <p className="muted">{last ? last.message : "요청 보내는 중"}…</p>
          </div>
        )}
        <div ref={bottom} />
      </div>
      <form className="composer" onSubmit={submit}>
        <input
          className="text-input"
          placeholder={`${item.title_ko || item.title}에 대해 물어보세요`}
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" disabled={busy || !text.trim()}>
          보내기
        </button>
      </form>
    </main>
  );
}

function ItemHeader({ item }: { item: Item }) {
  const facts = [
    item.proposers.length ? `제안자 ${item.proposers.join(", ")}` : null,
    item.year ? `${item.year}${item.year_uncertain ? " (불확실)" : ""}` : null,
    item.algs ? `공식 ${item.algs.split("\n")[0]}` : null,
    item.moves ? `평균 수 ${item.moves.split("\n")[0]}` : null,
  ].filter(Boolean);
  return (
    <header className="item-header">
      <div>
        <h2>
          {item.title_ko || item.title}{" "}
          <span className={`badge ${item.level === "입문" ? "badge-easy" : ""}`}>{item.level}</span>
        </h2>
        <p className="muted">
          {item.title_ko && <>{item.title} · </>}
          {facts.join(" · ")}
        </p>
      </div>
      <a href={item.url} target="_blank" rel="noreferrer" className="link">
        위키 원문
      </a>
    </header>
  );
}
