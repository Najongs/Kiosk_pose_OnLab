"""미니게임 공용 키포인트 헬퍼. 모두 PersonPose 를 받아 픽셀/각도 값을 준다."""

from __future__ import annotations

import math

from core.geometry import angle_at, select_coords
from core.pose_estimator import (
    LEFT_ANKLE,
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NOSE,
    RIGHT_ANKLE,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    PersonPose,
)

MIN_VIS = 0.3  # 이 미만 가시성 관절은 없는 것으로 취급


def _pt(p: PersonPose, i: int) -> tuple[float, float] | None:
    kp = p.keypoints
    if i >= len(kp) or kp[i, 2] < MIN_VIS:
        return None
    return float(kp[i, 0]), float(kp[i, 1])


def shoulder_width_px(p: PersonPose) -> float | None:
    ls, rs = _pt(p, LEFT_SHOULDER), _pt(p, RIGHT_SHOULDER)
    if ls is None or rs is None:
        return None
    return math.hypot(ls[0] - rs[0], ls[1] - rs[1])


def wrist_above_shoulder(p: PersonPose, margin_frac: float = 0.15) -> bool:
    """한쪽이라도 손목이 어깨보다 (어깨폭×margin) 이상 위에 있으면 True."""
    sw = shoulder_width_px(p)
    if sw is None:
        return False
    margin = sw * margin_frac
    for wi, si in ((LEFT_WRIST, LEFT_SHOULDER), (RIGHT_WRIST, RIGHT_SHOULDER)):
        w, s = _pt(p, wi), _pt(p, si)
        if w is not None and s is not None and w[1] < s[1] - margin:
            return True
    return False


def head_y(p: PersonPose) -> float | None:
    """머리(코) y 픽셀 좌표 (화면 위가 작다)."""
    n = _pt(p, NOSE)
    return None if n is None else n[1]


def torso_len_px(p: PersonPose) -> float | None:
    """어깨 중점 → 엉덩이 중점 픽셀 거리 (px→cm 근사 환산 기준)."""
    ls, rs = _pt(p, LEFT_SHOULDER), _pt(p, RIGHT_SHOULDER)
    lh, rh = _pt(p, LEFT_HIP), _pt(p, RIGHT_HIP)
    if None in (ls, rs, lh, rh):
        return None
    sx, sy = (ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2
    hx, hy = (lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2
    return math.hypot(sx - hx, sy - hy)


def elbow_angle(p: PersonPose) -> float | None:
    """팔꿈치 각도(도) — 보이는 팔들의 평균. 펴면 ~180, 굽히면 작아진다."""
    coords, vis = select_coords(p.keypoints, p.world_landmarks, prefer_world=True)
    angles = []
    for si, ei, wi in ((LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
                       (RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST)):
        if min(vis[si], vis[ei], vis[wi]) < MIN_VIS:
            continue
        a = angle_at(coords[si], coords[ei], coords[wi])
        if not math.isnan(a):
            angles.append(a)
    return sum(angles) / len(angles) if angles else None


def body_line_angle(p: PersonPose) -> float | None:
    """어깨-엉덩이-발목 일직선 각도(도). 곧게 편 자세(플랭크)면 ~180.
    좌우 중 더 굽은 쪽(min)을 반환 — 어느 쪽이든 처지면 경고해야 하므로."""
    coords, vis = select_coords(p.keypoints, p.world_landmarks, prefer_world=True)
    angles = []
    for si, hi, ai in ((LEFT_SHOULDER, LEFT_HIP, LEFT_ANKLE),
                       (RIGHT_SHOULDER, RIGHT_HIP, RIGHT_ANKLE)):
        if min(vis[si], vis[hi], vis[ai]) < MIN_VIS:
            continue
        a = angle_at(coords[si], coords[hi], coords[ai])
        if not math.isnan(a):
            angles.append(a)
    return min(angles) if angles else None
