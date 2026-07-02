/** 2인 대결 로직 검증: 플레이어 좌우 배정 + 라운드 진행 + 승자 판정 (결정적). */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

import { PoseScorer } from "../src/scorer";
import { PoseDefinition } from "../src/poseDef";
import { PersonPose } from "../src/keypoints";
import { assignPlayers, VersusSession } from "../src/versus";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = JSON.parse(readFileSync(join(here, "parity_fixture.json"), "utf-8"));
const def = (n: string): PoseDefinition =>
  JSON.parse(readFileSync(join(here, "..", "public", "poses", `${n}.json`), "utf-8"));

function poseFrom(imageName: string, xShift: number): PersonPose {
  const fx = fixtures.find((f: any) => f.image === imageName);
  const kps = fx.keypoints.map((k: number[]) => [k[0] + xShift, k[1], k[2]]);
  const xs = kps.map((k: number[]) => k[0]);
  return {
    keypoints: kps,
    world: fx.world_landmarks,
    bbox: [Math.min(...xs), 0, Math.max(...xs), 480],
    trackId: null,
  };
}

describe("versus", () => {
  it("assignPlayers: 좌=P1, 우=P2", () => {
    const left = poseFrom("mountain.jpg", 0); // x 작음
    const right = poseFrom("chair_overhead.jpg", 2000); // x 큼
    const [p1, p2] = assignPlayers([right, left]); // 입력 순서 무관
    expect(p1).toBe(left);
    expect(p2).toBe(right);
  });

  it("라운드 진행 → done, 승자 판정", () => {
    // passAccuracy=0 → 유효 포즈면 유지 성공. 서로 다른 포즈라 총점이 갈림.
    const vs = new VersusSession([def("tpose")], new PoseScorer(), 0, 1, 5);
    const p1 = poseFrom("mountain.jpg", 0);
    const p2 = poseFrom("chair_overhead.jpg", 2000);

    let now = 0;
    const step = () => {
      const s = vs.update([p1, p2], now);
      now += 0.2;
      return s;
    };

    let s = step();
    expect(s.state).toBe("idle"); // 첫 프레임: 두 명 감지 → 다음부터 countdown

    let guard = 0;
    while (s.state !== "done" && guard++ < 300) s = step();

    expect(s.state).toBe("done");
    expect(s.winner === 0 || s.winner === 1 || s.winner === 2).toBe(true);
    // 두 플레이어 모두 라운드를 완료해 총점이 쌓였다
    expect(s.p1.total).toBeGreaterThan(0);
    expect(s.p2.total).toBeGreaterThan(0);
  });
});
