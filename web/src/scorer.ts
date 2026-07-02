/** 각도 기반 스코어링 — 파이썬 core/scorer.py 와 동일 로직/점수곡선. */

import { angleAt, mean, vectorAngleToVertical, Vec } from "./geometry";
import { Metric, PoseDefinition, resolvePoint } from "./poseDef";
import { PersonPose } from "./keypoints";

export interface MetricScore {
  id: string;
  measured: number;
  target: number;
  score: number;
  valid: boolean;
  weight: number;
}

export interface ScoreResult {
  accuracy: number; // 0~100
  valid: boolean;
  jointScores: Record<string, MetricScore>;
}

/** err=|측정-목표|; score = max(0, 100*(1 - err/(2*tol))). */
function metricScore(measured: number, target: number, tolerance: number): number {
  const err = Math.abs(measured - target);
  return Math.max(0, 100 * (1 - err / (2 * Math.max(tolerance, 1e-6))));
}

export class PoseScorer {
  constructor(private minConf = 0.4) {}

  score(pose: PersonPose, def: PoseDefinition): ScoreResult {
    const kps = pose.keypoints;
    const vis = kps.map((k) => k[2]);
    const useWorld = (def.prefer_world ?? true) && pose.world !== null;
    const coords3 = pose.world;
    const coords2: Vec[] = kps.map((k) => [k[0], k[1]]);

    const jointScores: Record<string, MetricScore> = {};
    let totalW = 0;
    let accW = 0;

    for (const m of def.metrics) {
      const weight = m.weight ?? 1.0;
      let measured = NaN;
      let ok = false;
      if (m.type === "angle") {
        [measured, ok] = this.measureAngle(m, coords2, coords3, vis, useWorld);
      } else if (m.type === "lean") {
        [measured, ok] = this.measureLean(m, coords2, vis);
      }
      if (ok) {
        const s = metricScore(measured, m.target, m.tolerance);
        jointScores[m.id] = { id: m.id, measured, target: m.target, score: s, valid: true, weight };
        totalW += weight;
        accW += s * weight;
      } else {
        jointScores[m.id] = { id: m.id, measured: NaN, target: m.target, score: 0, valid: false, weight };
      }
    }

    const valid = totalW > 0;
    return { accuracy: valid ? accW / totalW : 0, valid, jointScores };
  }

  private pointCoord(idxs: number[], coords2: Vec[], coords3: number[][] | null, useWorld: boolean): Vec {
    const src = useWorld && coords3 ? coords3 : coords2;
    if (idxs.length === 1) return src[idxs[0]].slice();
    // 중점
    const pts = idxs.map((i) => src[i]);
    const dim = pts[0].length;
    const out = new Array(dim).fill(0);
    for (const p of pts) for (let d = 0; d < dim; d++) out[d] += p[d];
    return out.map((v) => v / pts.length);
  }

  private minVis(idxsList: number[][], vis: number[]): number {
    let m = Infinity;
    for (const idxs of idxsList) for (const i of idxs) m = Math.min(m, vis[i]);
    return isFinite(m) ? m : 0;
  }

  private measureAngle(
    m: Metric,
    coords2: Vec[],
    coords3: number[][] | null,
    vis: number[],
    useWorld: boolean,
  ): [number, boolean] {
    const sides = (m.side ?? "both") === "both" ? ["left", "right"] : [m.side!];
    const vals: number[] = [];
    for (const side of sides) {
      let ai: number[], bi: number[], ci: number[];
      try {
        ai = resolvePoint(m.joints![0], side);
        bi = resolvePoint(m.joints![1], side);
        ci = resolvePoint(m.joints![2], side);
      } catch {
        continue;
      }
      if (this.minVis([ai, bi, ci], vis) < this.minConf) continue;
      const a = this.pointCoord(ai, coords2, coords3, useWorld);
      const b = this.pointCoord(bi, coords2, coords3, useWorld);
      const c = this.pointCoord(ci, coords2, coords3, useWorld);
      const ang = angleAt(a, b, c);
      if (!Number.isNaN(ang)) vals.push(ang);
    }
    if (vals.length === 0) return [NaN, false];
    const agg = m.aggregate ?? "mean";
    if (agg === "min") return [Math.min(...vals), true];
    if (agg === "max") return [Math.max(...vals), true];
    return [mean(vals), true];
  }

  private measureLean(m: Metric, coords2: Vec[], vis: number[]): [number, boolean] {
    let ti: number[], bi: number[];
    try {
      ti = resolvePoint(m.top!);
      bi = resolvePoint(m.bottom!);
    } catch {
      return [NaN, false];
    }
    if (this.minVis([ti, bi], vis) < this.minConf) return [NaN, false];
    const top = this.pointCoord(ti, coords2, null, false);
    const bot = this.pointCoord(bi, coords2, null, false);
    const ang = vectorAngleToVertical(top, bot);
    if (Number.isNaN(ang)) return [NaN, false];
    return [ang, true];
  }
}
