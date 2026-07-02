/** 관절 각도/기하 유틸 — 파이썬 core/geometry.py 와 동일 로직. */

export type Vec = number[]; // 2D 또는 3D

function sub(a: Vec, b: Vec): Vec {
  return a.map((v, i) => v - b[i]);
}
function norm(a: Vec): number {
  return Math.sqrt(a.reduce((s, v) => s + v * v, 0));
}
function dot(a: Vec, b: Vec): number {
  return a.reduce((s, v, i) => s + v * b[i], 0);
}

/** 꼭짓점 b 에서 b->a 와 b->c 사이 각도(도). 2D/3D 모두 지원. */
export function angleAt(a: Vec, b: Vec, c: Vec): number {
  const ba = sub(a, b);
  const bc = sub(c, b);
  const nba = norm(ba);
  const nbc = norm(bc);
  if (nba < 1e-6 || nbc < 1e-6) return NaN;
  let cos = dot(ba, bc) / (nba * nbc);
  cos = Math.max(-1, Math.min(1, cos));
  return (Math.acos(cos) * 180) / Math.PI;
}

/** top->bottom 선분이 이미지 수직축과 이루는 기울기(도). 완전 수직이면 0. */
export function vectorAngleToVertical(top: Vec, bottom: Vec): number {
  const vx = top[0] - bottom[0];
  const vy = top[1] - bottom[1];
  const n = Math.sqrt(vx * vx + vy * vy);
  if (n < 1e-6) return NaN;
  // 수직 위 방향 (0,-1) 과의 각도
  let cos = (vx * 0 + vy * -1) / n;
  cos = Math.max(-1, Math.min(1, cos));
  return (Math.acos(cos) * 180) / Math.PI;
}

export function mean(vals: number[]): number {
  return vals.reduce((s, v) => s + v, 0) / vals.length;
}
