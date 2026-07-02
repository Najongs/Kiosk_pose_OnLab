/** 자세 정의 타입 + 로더 — 파이썬 core/pose_def.py 와 동일 스키마(JSON 공유). */

import { KEYPOINT_NAMES } from "./keypoints";

export interface Metric {
  id: string;
  type: "angle" | "lean";
  target: number;
  tolerance: number;
  weight?: number;
  joints?: string[];
  side?: "both" | "left" | "right";
  aggregate?: "mean" | "min" | "max";
  top?: string;
  bottom?: string;
}

export interface PoseDefinition {
  name: string;
  display_name: string;
  description?: string;
  prefer_world?: boolean;
  hold_seconds?: number;
  metrics: Metric[];
}

/**
 * 포인트 이름 → 키포인트 인덱스(들). len>1 이면 그 인덱스들의 중점 사용.
 * "<part>_mid" → 좌우 중점, side 접두사는 angle 관절 base 이름에 적용.
 */
export function resolvePoint(name: string, side?: string): number[] {
  if (name.endsWith("_mid")) {
    const base = name.slice(0, -4);
    return [KEYPOINT_NAMES[`left_${base}`], KEYPOINT_NAMES[`right_${base}`]];
  }
  if (side === "left" || side === "right") {
    const k = `${side}_${name}`;
    if (k in KEYPOINT_NAMES) return [KEYPOINT_NAMES[k]];
  }
  if (name in KEYPOINT_NAMES) return [KEYPOINT_NAMES[name]];
  throw new Error(`알 수 없는 포인트 이름: ${name} (side=${side})`);
}

const POSES_BASE = "poses";

export async function loadPose(name: string): Promise<PoseDefinition> {
  const res = await fetch(`${POSES_BASE}/${name}.json`);
  if (!res.ok) throw new Error(`자세 정의 로드 실패: ${name}`);
  return (await res.json()) as PoseDefinition;
}

export async function listPoses(): Promise<string[]> {
  const res = await fetch(`${POSES_BASE}/index.json`);
  if (!res.ok) return [];
  return (await res.json()) as string[];
}
