/** 유연성 리포트 분석 — 파이썬 core/report.py 와 동일 로직 (각도·등급·좌우 비대칭). */

import { angleAt, Vec } from "./geometry";
import { Metric, PoseDefinition, resolvePoint } from "./poseDef";
import { PersonPose } from "./keypoints";
import { MetricScore } from "./scorer";

export const ASYMMETRY_WARN_DEG = 12;

export interface MetricReport {
  id: string;
  measured: number;
  target: number;
  score: number;
  valid: boolean;
  left: number | null;
  right: number | null;
  asymmetry: number | null;
}
export interface PoseReport {
  name: string;
  score: number;
  grade: string;
  metrics: MetricReport[];
  maxAsymmetry: number | null;
  asymWarn: boolean;
}

export function grade(score: number): string {
  if (score >= 90) return "최상";
  if (score >= 75) return "우수";
  if (score >= 60) return "양호";
  return "개선 필요";
}

function angleSide(m: Metric, side: string, coords2: Vec[], coordsWorld: number[][] | null): number | null {
  let ai: number[], bi: number[], ci: number[];
  try {
    ai = resolvePoint(m.joints![0], side);
    bi = resolvePoint(m.joints![1], side);
    ci = resolvePoint(m.joints![2], side);
  } catch {
    return null;
  }
  const src = coordsWorld ?? coords2;
  const pt = (idxs: number[]): Vec => {
    if (idxs.length === 1) return src[idxs[0]];
    const dim = src[idxs[0]].length;
    const out = new Array(dim).fill(0);
    for (const i of idxs) for (let d = 0; d < dim; d++) out[d] += src[i][d];
    return out.map((v) => v / idxs.length);
  };
  const ang = angleAt(pt(ai), pt(bi), pt(ci));
  return Number.isNaN(ang) ? null : ang;
}

export function analyze(
  pose: PersonPose,
  def: PoseDefinition,
  jointScores: Record<string, MetricScore>,
  poseScore: number,
): PoseReport {
  const useWorld = (def.prefer_world ?? true) && pose.world !== null;
  const coordsWorld = useWorld ? pose.world : null;
  const coords2: Vec[] = pose.keypoints.map((k) => [k[0], k[1]]);

  const metrics: MetricReport[] = def.metrics.map((m) => {
    const js = jointScores[m.id];
    const entry: MetricReport = {
      id: m.id,
      measured: js ? js.measured : NaN,
      target: m.target,
      score: js ? js.score : 0,
      valid: js ? js.valid : false,
      left: null, right: null, asymmetry: null,
    };
    if (m.type === "angle" && (m.side ?? "both") === "both" && js && js.valid) {
      entry.left = angleSide(m, "left", coords2, coordsWorld);
      entry.right = angleSide(m, "right", coords2, coordsWorld);
      if (entry.left !== null && entry.right !== null)
        entry.asymmetry = Math.abs(entry.left - entry.right);
    }
    return entry;
  });

  const asyms = metrics.map((e) => e.asymmetry).filter((v): v is number => v !== null);
  const maxAsym = asyms.length ? Math.max(...asyms) : null;
  return {
    name: def.display_name,
    score: poseScore,
    grade: grade(poseScore),
    metrics,
    maxAsymmetry: maxAsym,
    asymWarn: maxAsym !== null && maxAsym >= ASYMMETRY_WARN_DEG,
  };
}
