import { useMemo, useState } from "react";
import { ApiError, searchItems } from "../api";
import type { Item, Level, SearchResult, Status } from "../types";

type LevelFilter = "전체" | Level;

interface Props {
  items: Item[];
  itemsError: string | null;
  status: Status | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function Sidebar({ items, itemsError, status, selectedId, onSelect }: Props) {
  const [level, setLevel] = useState<LevelFilter>("전체");
  const [keyword, setKeyword] = useState("");

  const visible = useMemo(() => {
    const k = keyword.trim().toLowerCase();
    return items.filter(
      (it) =>
        (level === "전체" || it.level === level) &&
        (!k || [it.title, it.title_ko, ...it.aliases].some((n) => n.toLowerCase().includes(k))),
    );
  }, [items, level, keyword]);

  return (
    <aside className="sidebar">
      <header className="brand">
        <span className="brand-mark" aria-hidden>
          ◩
        </span>
        <div>
          <h1>큐브 해법 코치</h1>
          <p>해법을 고르고 무엇이든 물어보세요</p>
        </div>
      </header>

      <ConditionSearch onSelect={onSelect} />

      <section className="panel list-panel">
        <div className="list-head">
          <h2>해법 목록</h2>
          <span className="muted">{visible.length}개</span>
        </div>
        <div className="segmented" role="tablist" aria-label="레벨 필터">
          {(["전체", "입문", "심화"] as LevelFilter[]).map((lv) => (
            <button key={lv} role="tab" aria-selected={level === lv} onClick={() => setLevel(lv)}>
              {lv}
            </button>
          ))}
        </div>
        <input
          className="text-input"
          placeholder="이름으로 찾기 (예: CFOP, CPLL)"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        {itemsError && <p className="notice error">{itemsError}</p>}
        <ul className="item-list">
          {visible.map((it) => (
            <li key={it.id}>
              <button className={it.id === selectedId ? "item active" : "item"} onClick={() => onSelect(it.id)}>
                <span className="item-title">{it.title_ko || it.title}</span>
                <span className="item-sub">
                  {it.title_ko ? it.title : it.aliases.slice(0, 2).join(", ")}
                </span>
                <span className={`badge ${it.level === "입문" ? "badge-easy" : ""}`}>{it.level}</span>
              </button>
            </li>
          ))}
          {!visible.length && !itemsError && <li className="muted empty">조건에 맞는 해법이 없습니다</li>}
        </ul>
      </section>

      <StatusBox status={status} />
    </aside>
  );
}

function ConditionSearch({ onSelect }: { onSelect: (id: string) => void }) {
  const [condition, setCondition] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!condition.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await searchItems(condition.trim()));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "조건 탐색 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>조건으로 찾기</h2>
      <form className="search-form" onSubmit={submit}>
        <input
          className="text-input"
          placeholder="예: 공식 적은 입문 해법"
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
        />
        <button type="submit" disabled={busy || !condition.trim()}>
          {busy ? "찾는 중" : "찾기"}
        </button>
      </form>
      {error && <p className="notice error">{error}</p>}
      {result && (
        <div className="cards">
          {result.notes.map((n) => (
            <p key={n} className="notice">
              {n}
            </p>
          ))}
          {result.cards.map((c) => (
            <button key={c.id} className="card" onClick={() => onSelect(c.id)}>
              <span className="card-title">
                {c.title_ko || c.title} <span className={`badge ${c.level === "입문" ? "badge-easy" : ""}`}>{c.level}</span>
              </span>
              <span className="card-meta">
                {c.algs && `공식 ${c.algs.split("\n")[0]}`}
                {c.moves && ` · 평균 수 ${c.moves.split("\n")[0]}`}
              </span>
              <span className="card-reason">{c.reason}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function StatusBox({ status }: { status: Status | null }) {
  if (!status) return null;
  return (
    <footer className="status">
      <div>
        색인: 항목 <b>{status.counts.cube_meta ?? 0}</b>건 · 문서 청크 <b>{status.counts.cube_docs ?? 0}</b>건
      </div>
      {status.counts.cube_meta === 0 && (
        <p className="notice warn">항목 색인이 0건입니다. index_items를 먼저 실행해 주세요.</p>
      )}
      {!status.api_key_set && <p className="notice warn">API 키가 설정되지 않았습니다 (.env의 GMS_KEY).</p>}
      {status.api_key_set && status.missing_env.length > 0 && (
        <p className="notice warn">.env에 비어 있는 값: {status.missing_env.join(", ")}</p>
      )}
    </footer>
  );
}
