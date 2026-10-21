import { Fragment } from "react";
import { sourceLabel } from "../lib/alg";
import type { ChatResult, Level } from "../types";
import { AlgCards } from "./AlgCard";

const CITE = /(\[근거\s*[\d,\s]+\])/g;
const IS_CITE = /^\[근거\s*[\d,\s]+\]$/; // test()용 — g 플래그 정규식은 lastIndex가 남아 번갈아 실패한다

/** 답변 본문 — [근거 N]을 작은 표시로 바꾸고 줄바꿈을 살린다 */
function AnswerText({ text }: { text: string }) {
  return (
    <div className="answer">
      {text.split("\n").map((line, i) => (
        <p key={i}>
          {line.split(CITE).map((part, j) =>
            IS_CITE.test(part) ? (
              <sup key={j} className="cite">
                {part.replace(/[[\]]/g, "").replace("근거", "").trim()}
              </sup>
            ) : (
              <Fragment key={j}>{part}</Fragment>
            ),
          )}
        </p>
      ))}
    </div>
  );
}

export function AnswerView({ result, level }: { result: ChatResult; level: Level }) {
  const { citations } = result;
  return (
    <>
      <AnswerText text={result.answer} />
      {result.no_citation && <p className="notice warn">이 답변은 근거 문서를 인용하지 않았습니다. 참고만 해 주세요.</p>}
      {result.notes.map((n) => (
        <p key={n} className="notice">
          {n}
        </p>
      ))}
      <AlgCards players={result.players ?? (result.player ? [result.player] : [])} level={level} />
      {citations.length > 0 && (
        <details className="citations">
          <summary>사용한 근거 {citations.length}건</summary>
          <ul>
            {citations.map((c) => (
              <li key={c.no}>
                <span className="cite">{c.no}</span>
                <span className="cite-title">{c.title}</span>
                <span className="muted"> · {sourceLabel(c.source_type)}</span>
                {c.url && (
                  <>
                    {" · "}
                    <a href={c.url} target="_blank" rel="noreferrer" className="link">
                      원문
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}
