"""참조 이미지에서 자세를 자동 등록.

각 참조 이미지에 MediaPipe 포즈추정을 돌려 관절 각도를 뽑고,
채점용 자세 정의(config/poses/<slug>.json)와 목표 예시(config/examples/<slug>.png)를
자동 생성한다. config/courses.json 에 '스트레칭' 코스도 추가하고, 웹앱
(web/public/)에도 동기화한다.

MediaPipe 가 원활한 환경(예: 윈도우 PC)에서 1회 실행:
    python tools/import_poses.py
매핑만 확인(추론 없이):
    python tools/import_poses.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.geometry import angle_at, vector_angle_to_vertical  # noqa: E402
from core.pose_def import resolve_point  # noqa: E402
from core.pose_estimator import KEYPOINT_NAMES  # noqa: E402
from core.refs import normalize_pose, pose_to_ref3d, set_ref, set_ref3d  # noqa: E402

TESTDATA = os.path.join(ROOT, "testdata")
POSES_DIR = os.path.join(ROOT, "config", "poses")
EXAMPLES_DIR = os.path.join(ROOT, "config", "examples")
COURSES = os.path.join(ROOT, "config", "courses.json")
WEB_POSES = os.path.join(ROOT, "web", "public", "poses")
WEB_EXAMPLES = os.path.join(ROOT, "web", "public", "examples")
WEB_COURSES = os.path.join(ROOT, "web", "public", "courses.json")

# (참조 이미지 파일명, slug(영문 id), 표시 이름(한글))
POSE_MAP: list[tuple[str, str, str]] = [
    ("깍지 끼고 바닥 찍기.png", "clasp_floor_touch", "깍지 끼고 바닥 찍기"),
    ("깍지끼고 등 뒤로 허리 숙여주기.png", "clasp_back_fold", "깍지 끼고 등 뒤로 허리 숙이기"),
    ("다리벌리고 허리 비틀기.png", "wide_twist", "다리 벌리고 허리 비틀기"),
    ("두손을 등 뒤로하여 늘려주기.png", "hands_behind", "두 손 등 뒤로 늘려주기"),
    ("두팔을 뒤로 한팔은 팔꿈치로 눌러주기.png", "arm_elbow_press", "두 팔 뒤로, 팔꿈치 눌러주기"),
    ("런지자세로 버티기.png", "lunge_hold", "런지 자세로 버티기"),
    ("목 좌우로 늘려주기.png", "neck_side", "목 좌우로 늘려주기"),
    ("손 깍지 끼고 앞으로 늘려주기.png", "clasp_forward", "손 깍지 끼고 앞으로 늘려주기"),
    ("손 깍지끼고 하늘보기.png", "clasp_sky", "손 깍지 끼고 하늘 보기"),
    ("한 다리 뒤로 들고 버티기.png", "leg_back_hold", "한 다리 뒤로 들고 버티기"),
    ("한 다리 들고 버티기.png", "leg_lift_hold", "한 다리 들고 버티기"),
    ("한팔 늘려주기.png", "arm_stretch", "한 팔 늘려주기"),
    ("허리 늘려주기.png", "waist_stretch", "허리 늘려주기"),
]

# (id 접두, 관절 3점 base 이름) — 좌/우 각각 목표를 만든다
ANGLE_METRICS = [
    ("shoulder", ["hip", "shoulder", "elbow"]),
    ("elbow", ["shoulder", "elbow", "wrist"]),
    ("hip", ["shoulder", "hip", "knee"]),
    ("knee", ["hip", "knee", "ankle"]),
]
MIN_VIS = 0.5
ANGLE_TOL = 28
LEAN_TOL = 15


def _imread(path: str):
    """유니코드(한글) 경로 안전 이미지 읽기. Windows 의 cv2.imread 는 한글 경로에서
    None 을 반환하므로 np.fromfile + imdecode 로 우회한다."""
    import cv2
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def build_metrics(pose) -> list[dict]:
    kps = pose.keypoints
    vis = kps[:, 2]
    world = pose.world_landmarks
    coords2 = kps[:, :2].astype(np.float64)
    src = world if world is not None else coords2

    metrics: list[dict] = []
    for base, joints in ANGLE_METRICS:
        for side in ("left", "right"):
            idxs = [resolve_point(j, side)[0] for j in joints]
            if min(vis[i] for i in idxs) < MIN_VIS:
                continue
            ang = angle_at(np.asarray(src[idxs[0]]), np.asarray(src[idxs[1]]),
                           np.asarray(src[idxs[2]]))
            if np.isnan(ang):
                continue
            metrics.append({"id": f"{base}_{side}", "type": "angle", "joints": joints,
                            "side": side, "target": round(float(ang), 1),
                            "tolerance": ANGLE_TOL, "weight": 1.0})
    # 몸통 기울기(2D)
    smid = (coords2[KEYPOINT_NAMES["left_shoulder"]] + coords2[KEYPOINT_NAMES["right_shoulder"]]) / 2
    hmid = (coords2[KEYPOINT_NAMES["left_hip"]] + coords2[KEYPOINT_NAMES["right_hip"]]) / 2
    lean = vector_angle_to_vertical(smid, hmid)
    if not np.isnan(lean):
        metrics.append({"id": "torso_lean", "type": "lean", "top": "shoulder_mid",
                        "bottom": "hip_mid", "target": round(float(lean), 1),
                        "tolerance": LEAN_TOL, "weight": 1.0})
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="추론 없이 매핑/파일 확인만")
    args = ap.parse_args()

    os.makedirs(POSES_DIR, exist_ok=True)
    os.makedirs(EXAMPLES_DIR, exist_ok=True)

    present = [(img, slug, disp) for img, slug, disp in POSE_MAP
               if os.path.isfile(os.path.join(TESTDATA, img))]
    missing = [img for img, _, _ in POSE_MAP if not os.path.isfile(os.path.join(TESTDATA, img))]
    print(f"대상 자세: {len(present)}개  (매핑 {len(POSE_MAP)}, 없음 {len(missing)})")
    for img in missing:
        print(f"  [없음] {img}")
    if args.dry_run:
        for _, slug, disp in present:
            print(f"  [예정] {slug:22s} <- {disp}")
        return 0

    from core.mediapipe_estimator import MediaPipeEstimator

    est = MediaPipeEstimator(static_image_mode=True)
    made: list[str] = []
    for img, slug, disp in present:
        frame = _imread(os.path.join(TESTDATA, img))
        if frame is None:
            print(f"  [읽기실패] {img} — 건너뜀")
            continue
        poses = est.estimate(frame)
        if not poses:
            print(f"  [검출실패] {disp} — 건너뜀")
            continue
        metrics = build_metrics(poses[0])
        if len(metrics) < 3:
            print(f"  [지표부족] {disp} — 관절 신뢰도 낮음, 건너뜀")
            continue
        definition = {
            "name": slug, "display_name": disp,
            "description": "참조 이미지에서 자동 생성", "prefer_world": True,
            "hold_seconds": 3.0, "metrics": metrics,
        }
        with open(os.path.join(POSES_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(definition, f, ensure_ascii=False, indent=2)
        shutil.copyfile(os.path.join(TESTDATA, img), os.path.join(EXAMPLES_DIR, f"{slug}.png"))
        # 참조 스켈레톤(2D+3D)도 저장 → '움직이는 캐릭터' 가이드에 사용
        set_ref(slug, normalize_pose(poses[0]))
        r3 = pose_to_ref3d(poses[0])
        if r3:
            set_ref3d(slug, r3)
        made.append(slug)
        print(f"  [생성] {slug:22s} 지표 {len(metrics)}개 (+참조 스켈레톤)  <- {disp}")
    est.close()

    if made:
        _update_courses(made)
        _sync_web(made)
    print(f"\n완료: 자세 {len(made)}개 생성. `python main.py --windowed` 로 확인하세요.")
    return 0


def _update_courses(slugs: list[str]) -> None:
    try:
        courses = json.load(open(COURSES, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        courses = []
    courses = [c for c in courses if c.get("id") != "stretch_video"]
    courses.append({
        "id": "stretch_video", "name": "스트레칭 세트", "difficulty": "중급",
        "desc": "영상 기반 전신 스트레칭", "poses": slugs,
    })
    json.dump(courses, open(COURSES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  코스 'stretch_video' 갱신 ({len(slugs)}개 자세)")


def _sync_web(slugs: list[str]) -> None:
    if not os.path.isdir(WEB_POSES):
        return
    os.makedirs(WEB_EXAMPLES, exist_ok=True)
    for slug in slugs:
        shutil.copyfile(os.path.join(POSES_DIR, f"{slug}.json"),
                        os.path.join(WEB_POSES, f"{slug}.json"))
        ex = os.path.join(EXAMPLES_DIR, f"{slug}.png")
        if os.path.isfile(ex):
            shutil.copyfile(ex, os.path.join(WEB_EXAMPLES, f"{slug}.png"))
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(WEB_POSES)
                   if f.endswith(".json") and f != "index.json")
    json.dump(names, open(os.path.join(WEB_POSES, "index.json"), "w", encoding="utf-8"))
    if os.path.isfile(COURSES):
        shutil.copyfile(COURSES, WEB_COURSES)
    print("  웹앱(web/public/) 동기화 완료")


if __name__ == "__main__":
    raise SystemExit(main())
