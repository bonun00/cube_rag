import { useEffect, useRef, useState } from "react";
import type { CubePlayerProps } from "./types";

type TwistyModule = typeof import("cubing/twisty");
type AlgModule = typeof import("cubing/alg");

let loading: Promise<[TwistyModule, AlgModule]> | null = null;
// cubing.js는 크므로 공식 카드가 처음 뜰 때 불러온다
const loadCubing = () => (loading ??= Promise.all([import("cubing/twisty"), import("cubing/alg")]));

/**
 * cubing.js TwistyPlayer. setup anchor = end → 공식을 다 돌리면 맞춰지는 상태에서 거꾸로 계산해,
 * 케이스(섞인 상태)에서 시작해 공식을 재생한다.
 */
export function TwistyCubePlayer({ alg }: CubePlayerProps) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<InstanceType<TwistyModule["TwistyPlayer"]> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    loadCubing()
      .then(([{ TwistyPlayer }, { Alg }]) => {
        if (cancelled || !host.current) return;
        try {
          Alg.fromString(alg); // 읽을 수 없는 표기면 여기서 실패
        } catch {
          setError("이 표기는 3D로 재생할 수 없습니다");
          player.current?.remove();
          player.current = null;
          return;
        }
        if (!player.current) {
          player.current = new TwistyPlayer({
            puzzle: "3x3x3",
            alg,
            experimentalSetupAnchor: "end",
            background: "none",
            controlPanel: "bottom-row",
            hintFacelets: "none",
          });
          host.current.appendChild(player.current);
        } else {
          player.current.alg = alg;
        }
      })
      .catch(() => !cancelled && setError("3D 플레이어를 불러오지 못했습니다"));
    return () => {
      cancelled = true;
    };
  }, [alg]);

  useEffect(
    () => () => {
      player.current?.remove();
      player.current = null;
    },
    [],
  );

  return (
    <div className="cube-player">
      <div ref={host} className="cube-host" />
      {error && <p className="notice warn">{error}</p>}
    </div>
  );
}
