/** 브라우저 포즈추정 — @mediapipe/tasks-vision(PoseLandmarker, WASM/GPU). */

import { FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";
import { NUM_KEYPOINTS, PersonPose } from "./keypoints";

export class PoseEstimatorMP {
  private constructor(private landmarker: PoseLandmarker) {}

  static async create(numPoses = 1): Promise<PoseEstimatorMP> {
    const fileset = await FilesetResolver.forVisionTasks("wasm");
    const landmarker = await PoseLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: "models/pose_landmarker_full.task",
        delegate: "GPU",
      },
      runningMode: "VIDEO",
      numPoses,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
    return new PoseEstimatorMP(landmarker);
  }

  estimate(video: HTMLVideoElement, tsMs: number): PersonPose[] {
    const w = video.videoWidth;
    const h = video.videoHeight;
    const res = this.landmarker.detectForVideo(video, tsMs);
    if (!res.landmarks || res.landmarks.length === 0) return [];

    const out: PersonPose[] = [];
    for (let pi = 0; pi < res.landmarks.length; pi++) {
      const lms = res.landmarks[pi];
      const kps: number[][] = [];
      for (let i = 0; i < NUM_KEYPOINTS && i < lms.length; i++) {
        const lm = lms[i];
        kps.push([lm.x * w, lm.y * h, lm.visibility ?? 1.0]);
      }
      let world: number[][] | null = null;
      const wl = res.worldLandmarks?.[pi];
      if (wl) {
        world = [];
        for (let i = 0; i < NUM_KEYPOINTS && i < wl.length; i++) {
          world.push([wl[i].x, wl[i].y, wl[i].z]);
        }
      }
      out.push({ keypoints: kps, world, bbox: bboxOf(kps, w, h), trackId: null });
    }
    return out;
  }

  close(): void {
    this.landmarker.close();
  }
}

function bboxOf(kps: number[][], w: number, h: number): [number, number, number, number] {
  const vis = kps.filter((k) => k[2] >= 0.3);
  const pts = vis.length ? vis : kps;
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  for (const k of pts) {
    x1 = Math.min(x1, k[0]); y1 = Math.min(y1, k[1]);
    x2 = Math.max(x2, k[0]); y2 = Math.max(y2, k[1]);
  }
  const cl = (v: number, m: number) => Math.max(0, Math.min(m, v));
  return [cl(x1, w), cl(y1, h), cl(x2, w), cl(y2, h)];
}

/** 군중 속 주 대상: bbox 면적 최대(단순 버전; 필요시 IoU 추적으로 확장). */
export function pickPrimary(poses: PersonPose[]): PersonPose | null {
  if (poses.length === 0) return null;
  let best = poses[0];
  let bestArea = area(best.bbox);
  for (const p of poses) {
    const a = area(p.bbox);
    if (a > bestArea) { best = p; bestArea = a; }
  }
  best.trackId = 1;
  return best;
}
function area(b: [number, number, number, number]): number {
  return Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
}
