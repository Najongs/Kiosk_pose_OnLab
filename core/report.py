"""유연성 리포트 분석: 완료된 자세의 관절 각도(ROM)·등급·좌우 비대칭 산출.

세션에서 자세 유지 성공 순간의 포즈와 채점 결과를 받아, 사용자에게 보여줄
리포트 항목을 만든다. 좌우 대칭 각도 지표는 왼/오른쪽을 따로 계산해 차이를 낸다.
"""

from __future__ import annotations

import numpy as np

from .geometry import angle_at
from .pose_def import PoseDefinition, resolve_point
from .pose_estimator import PersonPose
from .scorer import MetricScore

ASYMMETRY_WARN_DEG = 12.0  # 좌우 차이가 이 이상이면 경고


def grade(score: float) -> str:
    if score >= 90:
        return "최상"
    if score >= 75:
        return "우수"
    if score >= 60:
        return "양호"
    return "개선 필요"


def _angle_side(m, side: str, coords2: np.ndarray, coords_world) -> float | None:
    try:
        ai = resolve_point(m.joints[0], side)
        bi = resolve_point(m.joints[1], side)
        ci = resolve_point(m.joints[2], side)
    except (KeyError, IndexError):
        return None
    src = coords_world if coords_world is not None else coords2

    def pt(idxs):
        return src[idxs[0]] if len(idxs) == 1 else src[idxs].mean(axis=0)

    ang = angle_at(np.asarray(pt(ai)), np.asarray(pt(bi)), np.asarray(pt(ci)))
    return None if np.isnan(ang) else float(ang)


def analyze(pose: PersonPose, pose_def: PoseDefinition,
            joint_scores: dict[str, MetricScore], pose_score: float) -> dict:
    use_world = pose_def.prefer_world and pose.world_landmarks is not None
    coords_world = pose.world_landmarks if use_world else None
    coords2 = pose.keypoints[:, :2].astype(np.float64)

    metrics = []
    for m in pose_def.metrics:
        js = joint_scores.get(m.id)
        entry = {
            "id": m.id,
            "measured": js.measured if js else float("nan"),
            "target": m.target,
            "score": js.score if js else 0.0,
            "valid": bool(js.valid) if js else False,
            "left": None, "right": None, "asymmetry": None,
        }
        if m.type == "angle" and m.side == "both" and js and js.valid:
            left = _angle_side(m, "left", coords2, coords_world)
            right = _angle_side(m, "right", coords2, coords_world)
            entry["left"] = left
            entry["right"] = right
            if left is not None and right is not None:
                entry["asymmetry"] = abs(left - right)
        metrics.append(entry)

    max_asym = max((e["asymmetry"] for e in metrics if e["asymmetry"] is not None),
                   default=None)
    return {
        "name": pose_def.display_name,
        "score": pose_score,
        "grade": grade(pose_score),
        "metrics": metrics,
        "max_asymmetry": max_asym,
        "asym_warn": max_asym is not None and max_asym >= ASYMMETRY_WARN_DEG,
    }
