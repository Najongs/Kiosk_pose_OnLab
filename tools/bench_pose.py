"""포즈 모델 안정성·속도 벤치마크 — lite/full/heavy × 스무딩 유무.

같은 이미지에 카메라 노이즈를 흉내 낸 픽셀 노이즈를 얹어 N 프레임 연속
추론하고, 키포인트가 프레임 간 얼마나 떨리는지(std)와 프레임당 추론
시간을 잰다. 실제 카메라 떨림의 근사이지만 모델·필터 간 상대 비교에는 충분.

실행: python tools/bench_pose.py [--frames 40]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from core.frame_source import imread_unicode
from core.mediapipe_estimator import MediaPipeEstimator, resolve_model
from core.smoothing import PoseSmoother

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 떨림 측정 대상 관절: 코, 손목, 발목 (말단일수록 떨림이 심함)
JOINTS = (0, 15, 16, 27, 28)


def bench_variant(variant: str, img: np.ndarray, frames: int,
                  rng: np.random.RandomState) -> dict | None:
    path = resolve_model(variant)
    if os.path.basename(path) != f"pose_landmarker_{variant}.task":
        return None  # 해당 변형 모델 파일 없음
    est = MediaPipeEstimator(model_variant=variant, async_infer=False)
    sm = PoseSmoother()
    raw_pts, sm_pts, times = [], [], []
    for i in range(frames):
        noise = rng.normal(0, 6, img.shape).astype(np.int16)
        frame = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        t0 = time.perf_counter()
        poses = est.estimate(frame)
        times.append((time.perf_counter() - t0) * 1000)
        if not poses:
            continue
        p = poses[0]
        raw_pts.append(p.keypoints[JOINTS, :2].copy())
        sp = sm.apply(p, i / 30.0)
        sm_pts.append(sp.keypoints[JOINTS, :2].copy())
    est.close()
    if len(raw_pts) < frames * 0.8:
        return {"detect_rate": len(raw_pts) / frames}

    def jitter(pts):  # 관절별 x/y 표준편차의 평균 (px)
        a = np.stack(pts[5:])  # 워밍업 5프레임 제외
        return float(np.mean(a.std(axis=0)))

    return {
        "detect_rate": len(raw_pts) / frames,
        "jitter_raw": jitter(raw_pts),
        "jitter_smoothed": jitter(sm_pts),
        "ms": float(np.mean(times[3:])),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--image", default=os.path.join(ROOT, "testdata", "mountain.jpg"))
    args = ap.parse_args()

    img = imread_unicode(args.image)
    if img is None:
        print(f"이미지를 열 수 없음: {args.image}")
        return 1
    img = cv2.resize(img, (960, int(img.shape[0] * 960 / img.shape[1])))

    print(f"{'모델':<8}{'검출률':>8}{'떨림(raw)':>12}{'떨림(필터)':>12}{'추론 ms':>10}")
    for variant in ("lite", "full", "heavy"):
        rng = np.random.RandomState(42)  # 변형 간 동일한 노이즈
        r = bench_variant(variant, img, args.frames, rng)
        if r is None:
            print(f"{variant:<8}{'(모델 없음)':>8}")
            continue
        if "jitter_raw" not in r:
            print(f"{variant:<8}{r['detect_rate']:>7.0%}   검출 실패 다수")
            continue
        print(f"{variant:<8}{r['detect_rate']:>7.0%}"
              f"{r['jitter_raw']:>11.2f}px{r['jitter_smoothed']:>11.2f}px"
              f"{r['ms']:>9.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
