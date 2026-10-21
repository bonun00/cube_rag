import { useState } from "react";
import { cleanAlg } from "../lib/alg";
import type { Level, Player } from "../types";
import { CubePlayer } from "./cube/CubePlayer";

/**
 * 케이스별 공식 카드. 케이스가 여러 개면 위에 케이스 탭을 두고 하나씩 재생한다
 * (3D 플레이어를 동시에 여러 개 띄우면 무거워서).
 */
export function AlgCards({ players, level }: { players: Player[]; level: Level }) {
  const [index, setIndex] = useState(0);
  if (!players.length) return null;
  const current = players[Math.min(index, players.length - 1)];

  return (
    <div className="alg-cards">
      {players.length > 1 && (
        <div className="segmented case-tabs" role="tablist" aria-label="케이스">
          {players.map((p, i) => (
            <button key={p.case} role="tab" aria-selected={i === index} onClick={() => setIndex(i)}>
              {p.case.replace(/ Permutation$/, "")}
            </button>
          ))}
        </div>
      )}
      <AlgCard key={current.case} player={current} level={level} />
    </div>
  );
}

/** 공식 카드 — 고른 공식(입문 1개, 심화 최대 3개) 중 하나를 3D로 재생 + 시연 영상 링크 */
export function AlgCard({ player, level }: { player: Player; level: Level }) {
  const [index, setIndex] = useState(0);
  const current = player.algs[Math.min(index, player.algs.length - 1)];

  return (
    <section className="alg-card">
      <header>
        <h3>{player.case}</h3>
        <span className="muted">{level === "입문" ? "입문 추천 공식" : `추천 공식 ${player.algs.length}개`}</span>
      </header>
      {player.inferred && (
        <p className="muted alg-source">질문에 나온 케이스라 위키 공식 목록에서 가져온 공식입니다.</p>
      )}
      {player.algs.length > 1 && (
        <div className="segmented small" role="tablist">
          {player.algs.map((a, i) => (
            <button key={a.alg} role="tab" aria-selected={i === index} onClick={() => setIndex(i)}>
              공식 {i + 1}
            </button>
          ))}
        </div>
      )}
      <CubePlayer alg={cleanAlg(current.alg)} />
      <code className="alg-text">{current.alg}</code>
      {current.video && (
        <a className="link" href={current.video} target="_blank" rel="noreferrer">
          시연 영상 보기 ↗
        </a>
      )}
    </section>
  );
}
