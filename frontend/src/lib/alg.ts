/**
 * 위키 공식 표기 → 재생용 표기.
 * (U') (y) 같은 괄호는 벗긴다. 뒤에 반복 횟수가 붙은 (R U R' U')2 는 cubing.js가 반복으로 읽으므로 그대로 둔다.
 */
export function cleanAlg(alg: string): string {
  let s = alg.replace(/[’′‘`]/g, "'");
  for (let i = 0; i < 5; i++) {
    const next = s.replace(/\(([^()]*)\)(?!\d)/g, " $1 ");
    if (next === s) break;
    s = next;
  }
  return s.replace(/\s+/g, " ").trim();
}

const SOURCE_LABELS: Record<string, string> = {
  item_meta: "항목 정보",
  speedsolving_wiki: "Speedsolving Wiki",
  cubetorial: "큐토리얼",
};

export const sourceLabel = (type: string) => SOURCE_LABELS[type] ?? type;
