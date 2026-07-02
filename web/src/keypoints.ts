/**
 * 33 키포인트 인덱스 (MediaPipe Pose) — 파이썬 core/pose_estimator.py 와 동일.
 * 상위 로직이 모델에 독립되도록 이름→인덱스 매핑을 제공한다.
 */

export const NOSE = 0;
export const LEFT_SHOULDER = 11;
export const RIGHT_SHOULDER = 12;
export const LEFT_ELBOW = 13;
export const RIGHT_ELBOW = 14;
export const LEFT_WRIST = 15;
export const RIGHT_WRIST = 16;
export const LEFT_HIP = 23;
export const RIGHT_HIP = 24;
export const LEFT_KNEE = 25;
export const RIGHT_KNEE = 26;
export const LEFT_ANKLE = 27;
export const RIGHT_ANKLE = 28;
export const LEFT_HEEL = 29;
export const RIGHT_HEEL = 30;
export const LEFT_FOOT_INDEX = 31;
export const RIGHT_FOOT_INDEX = 32;

export const NUM_KEYPOINTS = 33;

export const KEYPOINT_NAMES: Record<string, number> = {
  nose: NOSE,
  left_shoulder: LEFT_SHOULDER,
  right_shoulder: RIGHT_SHOULDER,
  left_elbow: LEFT_ELBOW,
  right_elbow: RIGHT_ELBOW,
  left_wrist: LEFT_WRIST,
  right_wrist: RIGHT_WRIST,
  left_hip: LEFT_HIP,
  right_hip: RIGHT_HIP,
  left_knee: LEFT_KNEE,
  right_knee: RIGHT_KNEE,
  left_ankle: LEFT_ANKLE,
  right_ankle: RIGHT_ANKLE,
  left_heel: LEFT_HEEL,
  right_heel: RIGHT_HEEL,
  left_foot_index: LEFT_FOOT_INDEX,
  right_foot_index: RIGHT_FOOT_INDEX,
};

export const SKELETON_EDGES: [number, number][] = [
  [LEFT_SHOULDER, RIGHT_SHOULDER],
  [LEFT_SHOULDER, LEFT_ELBOW],
  [LEFT_ELBOW, LEFT_WRIST],
  [RIGHT_SHOULDER, RIGHT_ELBOW],
  [RIGHT_ELBOW, RIGHT_WRIST],
  [LEFT_SHOULDER, LEFT_HIP],
  [RIGHT_SHOULDER, RIGHT_HIP],
  [LEFT_HIP, RIGHT_HIP],
  [LEFT_HIP, LEFT_KNEE],
  [LEFT_KNEE, LEFT_ANKLE],
  [RIGHT_HIP, RIGHT_KNEE],
  [RIGHT_KNEE, RIGHT_ANKLE],
  [LEFT_ANKLE, LEFT_FOOT_INDEX],
  [RIGHT_ANKLE, RIGHT_FOOT_INDEX],
];

/** 한 사람의 포즈. keypoints[i] = [x_px, y_px, visibility], world[i] = [x,y,z] (m). */
export interface PersonPose {
  keypoints: number[][]; // (33,3)
  world: number[][] | null; // (33,3) | null
  bbox: [number, number, number, number];
  trackId: number | null;
}
