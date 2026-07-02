/**
 * 패리티 테스트: 동일한 키포인트에 대해 JS 스코어러가 파이썬과 같은 점수를 내는지 검증.
 * fixture(parity_fixture.json)는 파이썬 core/scorer.py 로 생성한 정답값.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

import { PoseScorer } from "../src/scorer";
import { PoseDefinition } from "../src/poseDef";
import { PersonPose } from "../src/keypoints";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = JSON.parse(readFileSync(join(here, "parity_fixture.json"), "utf-8"));

function loadDef(name: string): PoseDefinition {
  return JSON.parse(readFileSync(join(here, "..", "public", "poses", `${name}.json`), "utf-8"));
}

describe("scorer parity (JS vs Python)", () => {
  const scorer = new PoseScorer(0.4);

  for (const fx of fixtures) {
    it(`${fx.image} vs ${fx.pose}`, () => {
      const pose: PersonPose = {
        keypoints: fx.keypoints,
        world: fx.world_landmarks,
        bbox: [0, 0, 0, 0],
        trackId: null,
      };
      const def = loadDef(fx.pose);
      const r = scorer.score(pose, def);

      expect(r.accuracy).toBeCloseTo(fx.expected_accuracy, 2);
      for (const [id, exp] of Object.entries<any>(fx.expected_metrics)) {
        const got = r.jointScores[id];
        expect(got.valid).toBe(exp.valid);
        if (exp.valid) {
          expect(got.measured).toBeCloseTo(exp.measured, 2);
          expect(got.score).toBeCloseTo(exp.score, 2);
        }
      }
    });
  }
});
