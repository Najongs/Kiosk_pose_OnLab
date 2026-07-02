"""헤드리스 검증 도구.

이미지/폴더/영상을 입력받아 포즈 추정 → (선택)추적 → (선택)스코어링 결과를
프레임에 그려 파일로 저장한다. 서버에 디스플레이가 없어도 결과 PNG/MP4 를
열어 눈으로 검증할 수 있다.

사용법:
    python -m tools.demo_overlay <입력경로> [--pose forward_bend] [--out out/]
    python tools/demo_overlay.py testdata/ --out out/
"""

from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.frame_source import ImageSource, open_source  # noqa: E402
from core.mediapipe_estimator import MediaPipeEstimator  # noqa: E402
from core.pose_estimator import SKELETON_EDGES, PersonPose  # noqa: E402
from core.tracker import PrimarySubjectTracker  # noqa: E402


def draw_pose(frame: np.ndarray, pose: PersonPose, vis_thresh: float = 0.3) -> None:
    kps = pose.keypoints
    # 뼈대
    for a, b in SKELETON_EDGES:
        if kps[a, 2] >= vis_thresh and kps[b, 2] >= vis_thresh:
            pa = (int(kps[a, 0]), int(kps[a, 1]))
            pb = (int(kps[b, 0]), int(kps[b, 1]))
            cv2.line(frame, pa, pb, (0, 255, 0), 2)
    # 관절점
    for i in range(len(kps)):
        if kps[i, 2] >= vis_thresh:
            cv2.circle(frame, (int(kps[i, 0]), int(kps[i, 1])), 3, (0, 128, 255), -1)
    # bbox
    x1, y1, x2, y2 = (int(v) for v in pose.bbox)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
    if pose.track_id is not None:
        cv2.putText(frame, f"ID {pose.track_id}", (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)


def put_lines(frame: np.ndarray, lines: list[str], org=(10, 30)) -> None:
    x, y = org
    for i, text in enumerate(lines):
        yy = y + i * 28
        cv2.putText(frame, text, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, text, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 1, cv2.LINE_AA)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="이미지 파일/폴더 또는 영상 파일")
    ap.add_argument("--out", default="out", help="결과 저장 폴더")
    ap.add_argument("--pose", default=None, help="채점할 자세 이름(config/poses/<name>.json)")
    ap.add_argument("--no-track", action="store_true", help="주 대상 추적 비활성화")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    src = open_source(args.input)
    is_image = isinstance(src, ImageSource)

    estimator = MediaPipeEstimator(static_image_mode=is_image)
    tracker = None if args.no_track else PrimarySubjectTracker()

    scorer = None
    pose_def = None
    if args.pose:
        from core.pose_def import load_pose  # 지연 임포트
        from core.scorer import PoseScorer
        pose_def = load_pose(args.pose)
        scorer = PoseScorer()

    frame_idx = 0
    writer = None
    detected_frames = 0
    while True:
        frame = src.read()
        if frame is None:
            break
        poses = estimator.estimate(frame)
        if tracker is not None:
            primary = tracker.update(poses)
            poses = [primary] if primary is not None else []
        if poses:
            detected_frames += 1

        for pose in poses:
            draw_pose(frame, pose)

        lines = [f"persons: {len(poses)}"]
        if scorer is not None and pose_def is not None and poses:
            result = scorer.score(poses[0], pose_def)
            lines.append(f"{pose_def.name}: {result.accuracy:.0f}%")
            for jn, ja in result.joint_scores.items():
                lines.append(f"  {jn}: {ja.measured:.0f}deg -> {ja.score:.0f}%")
        put_lines(frame, lines)

        if is_image:
            name = os.path.basename(getattr(src, "last_path", f"frame_{frame_idx}.png"))
            base, _ = os.path.splitext(name)
            out_path = os.path.join(args.out, f"{base}_overlay.png")
            cv2.imwrite(out_path, frame)
            print(f"saved {out_path}  (persons={len(poses)})")
        else:
            if writer is None:
                h, w = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_path = os.path.join(args.out, "overlay.mp4")
                writer = cv2.VideoWriter(out_path, fourcc, 25.0, (w, h))
            writer.write(frame)
        frame_idx += 1

    if writer is not None:
        writer.release()
        print(f"saved {os.path.join(args.out, 'overlay.mp4')}")
    estimator.close()
    print(f"done: {frame_idx} frames, detections in {detected_frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
