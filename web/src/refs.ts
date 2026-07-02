/** 목표 자세 참조 스켈레톤 저장 (관리자 캡처 → 가이드 오버레이에 사용).
 * 정규화 좌표(bbox 기준 0~1, 33x2)로 저장해 화면 크기와 무관하게 재사용. */

import { PersonPose } from "./keypoints";

const KEY = "onlab.refs";
const VIS = 0.3;

type RefMap = Record<string, number[][]>; // poseName -> 33x2 (normalized)

function loadMap(): RefMap {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as RefMap;
  } catch {
    return {};
  }
}

export function getRef(pose: string): number[][] | null {
  return loadMap()[pose] ?? null;
}

export function setRef(pose: string, normalized: number[][]): void {
  const m = loadMap();
  m[pose] = normalized;
  localStorage.setItem(KEY, JSON.stringify(m));
}

export function clearRef(pose: string): void {
  const m = loadMap();
  delete m[pose];
  localStorage.setItem(KEY, JSON.stringify(m));
}

export function hasRef(pose: string): boolean {
  return getRef(pose) !== null;
}

/** 라이브 포즈를 bbox 기준 0~1 로 정규화 (저장용). visibility 유지. */
export function normalizePose(pose: PersonPose): number[][] {
  const [x1, y1, x2, y2] = pose.bbox;
  const w = Math.max(1, x2 - x1);
  const h = Math.max(1, y2 - y1);
  return pose.keypoints.map((k) => [
    (k[0] - x1) / w,
    (k[1] - y1) / h,
    k[2],
  ]);
}

export { VIS as REF_VIS };
