"""각도 기반 스코어링.

자세 정의(PoseDefinition)의 각 지표를 라이브 포즈에서 측정하고, 목표값 대비
오차를 점수로 환산한다. 각도 기반이라 신체 크기·화면 위치에 불변이며,
신뢰도가 낮은 관절(occlusion)은 자동으로 제외해 겹침 환경에 대응한다.

점수 곡선(지표별): err = |측정값 - 목표|
    score = max(0, 100 * (1 - err / (2 * tolerance)))
    → err=0 이면 100점, err=tolerance 면 50점, err>=2*tolerance 면 0점.
정확도 = 유효 지표들의 가중 평균.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import angle_at, midpoint, vector_angle_to_vertical
from .pose_def import Metric, PoseDefinition, resolve_point
from .pose_estimator import PersonPose


@dataclass
class MetricScore:
    id: str
    measured: float
    target: float
    score: float
    valid: bool
    weight: float


@dataclass
class ScoreResult:
    accuracy: float  # 0~100
    valid: bool
    joint_scores: dict[str, MetricScore] = field(default_factory=dict)


def _metric_score(measured: float, target: float, tolerance: float) -> float:
    err = abs(measured - target)
    return max(0.0, 100.0 * (1.0 - err / (2.0 * max(tolerance, 1e-6))))


class PoseScorer:
    def __init__(self, min_keypoint_confidence: float = 0.4):
        self.min_conf = min_keypoint_confidence

    def score(self, pose: PersonPose, pose_def: PoseDefinition) -> ScoreResult:
        kps = pose.keypoints
        vis = kps[:, 2]
        use_world = pose_def.prefer_world and pose.world_landmarks is not None
        coords3 = pose.world_landmarks if use_world else None
        coords2 = kps[:, :2].astype(np.float64)

        scores: dict[str, MetricScore] = {}
        total_w = 0.0
        acc_w = 0.0

        for m in pose_def.metrics:
            if m.type == "angle":
                measured, ok = self._measure_angle(m, coords2, coords3, vis, use_world)
            elif m.type == "lean":
                measured, ok = self._measure_lean(m, coords2, vis)
            else:
                measured, ok = float("nan"), False

            if ok:
                s = _metric_score(measured, m.target, m.tolerance)
                scores[m.id] = MetricScore(m.id, measured, m.target, s, True, m.weight)
                total_w += m.weight
                acc_w += s * m.weight
            else:
                scores[m.id] = MetricScore(m.id, float("nan"), m.target, 0.0, False, m.weight)

        valid = total_w > 0
        accuracy = (acc_w / total_w) if valid else 0.0
        return ScoreResult(accuracy=accuracy, valid=valid, joint_scores=scores)

    # --- 지표별 측정 ---

    def _point(self, idxs: list[int], coords2, coords3, use_world):
        """포인트(단일 관절 또는 중점)의 좌표와 최소 visibility 를 반환."""
        src = coords3 if use_world else coords2
        pts = src[idxs]
        pos = pts.mean(axis=0) if len(idxs) > 1 else pts[0]
        return pos

    def _min_vis(self, idxs_list: list[list[int]], vis) -> float:
        allidx = [i for idxs in idxs_list for i in idxs]
        return float(min(vis[i] for i in allidx)) if allidx else 0.0

    def _measure_angle(self, m: Metric, coords2, coords3, vis, use_world):
        sides = ["left", "right"] if m.side == "both" else [m.side]
        vals = []
        for side in sides:
            try:
                ai = resolve_point(m.joints[0], side)
                bi = resolve_point(m.joints[1], side)
                ci = resolve_point(m.joints[2], side)
            except KeyError:
                continue
            if self._min_vis([ai, bi, ci], vis) < self.min_conf:
                continue
            a = self._point(ai, coords2, coords3, use_world)
            b = self._point(bi, coords2, coords3, use_world)
            c = self._point(ci, coords2, coords3, use_world)
            ang = angle_at(np.asarray(a), np.asarray(b), np.asarray(c))
            if not np.isnan(ang):
                vals.append(ang)
        if not vals:
            return float("nan"), False
        if m.aggregate == "min":
            return float(np.min(vals)), True
        if m.aggregate == "max":
            return float(np.max(vals)), True
        return float(np.mean(vals)), True

    def _measure_lean(self, m: Metric, coords2, vis):
        # 몸통 기울기는 이미지 수직축 기준이 자연스러우므로 항상 2D 좌표 사용.
        try:
            ti = resolve_point(m.top)
            bi = resolve_point(m.bottom)
        except KeyError:
            return float("nan"), False
        if self._min_vis([ti, bi], vis) < self.min_conf:
            return float("nan"), False
        top = coords2[ti].mean(axis=0) if len(ti) > 1 else coords2[ti[0]]
        bot = coords2[bi].mean(axis=0) if len(bi) > 1 else coords2[bi[0]]
        ang = vector_angle_to_vertical(np.asarray(top), np.asarray(bot))
        if np.isnan(ang):
            return float("nan"), False
        return float(ang), True
