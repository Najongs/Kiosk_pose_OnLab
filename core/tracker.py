"""주 대상 1명 선택·추적.

군중/겹침 환경에서 '평가 대상' 한 명을 고른다:
  - 후보 중 bbox 면적이 크고(가까움) 화면 중앙에 가까운 사람에 높은 점수.
  - 프레임 간에는 직전 주 대상과의 IoU/중심거리로 동일인을 유지해 흔들림 방지.
  - 주 대상이 잠깐 사라져도 grace_frames 동안 유지하다가 재선택.

MediaPipe 백엔드는 프레임당 1명만 주지만, YOLO 등 다중 인물 백엔드로 교체해도
이 추적기가 그대로 주 대상을 골라낸다.
"""

from __future__ import annotations

from .pose_estimator import PersonPose


def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 1e-6 else 0.0


class PrimarySubjectTracker:
    def __init__(self, center_weight: float = 0.3, min_iou_keep: float = 0.2,
                 grace_frames: int = 15):
        self.center_weight = center_weight
        self.min_iou_keep = min_iou_keep
        self.grace_frames = grace_frames
        self._current: PersonPose | None = None
        self._current_bbox: tuple | None = None
        self._misses = 0
        self._next_id = 1

    def update(self, poses: list[PersonPose]) -> PersonPose | None:
        if not poses:
            self._misses += 1
            if self._misses > self.grace_frames:
                self._current = None
                self._current_bbox = None
            return None

        chosen: PersonPose | None = None

        # 1) 직전 주 대상과 가장 잘 겹치는 후보를 우선 유지
        if self._current_bbox is not None:
            best_iou, best = 0.0, None
            for p in poses:
                iou = _iou(self._current_bbox, p.bbox)
                if iou > best_iou:
                    best_iou, best = iou, p
            if best is not None and best_iou >= self.min_iou_keep:
                chosen = best

        # 2) 없으면 salience(크기+중앙) 최대 후보를 새 주 대상으로 선택
        if chosen is None:
            chosen = max(poses, key=self._salience)
            chosen.track_id = self._next_id
            self._next_id += 1
        else:
            chosen.track_id = self._current.track_id if self._current else self._next_id

        self._current = chosen
        self._current_bbox = chosen.bbox
        self._misses = 0
        return chosen

    def _salience(self, pose: PersonPose) -> float:
        area = pose.bbox_area
        # 화면 정보가 없으므로 중앙성은 후보 간 상대 비교로 처리하기 어렵다.
        # 여기선 면적 우선 + track_id 안정성만으로 충분(단일 프레임 최댓값 선택).
        # 화면 크기를 아는 상위에서 center_weight 를 쓰고 싶다면 salience 를 오버라이드.
        return area
