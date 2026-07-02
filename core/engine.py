"""파이프라인 엔진.

한 프레임을 받아 [포즈 추정 → 주 대상 추적 → 세션 갱신] 을 수행하고
(주 대상 포즈, 세션 상태) 를 반환한다. 화면 합성(compose)은 UI 계층에서
호출하므로 core 가 ui 에 의존하지 않는다.

Qt 앱과 헤드리스 검증 도구가 동일한 엔진을 공유한다.
"""

from __future__ import annotations

import json
import os

from .mediapipe_estimator import MediaPipeEstimator
from .pose_estimator import PersonPose
from .scorer import PoseScorer
from .session import Session, SessionState
from .tracker import PrimarySubjectTracker

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS = os.path.join(_ROOT, "config", "settings.json")


def load_settings(path: str = _SETTINGS) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Engine:
    def __init__(self, pose_names: list[str], settings: dict | None = None,
                 static_image_mode: bool = False, app_config: dict | None = None,
                 reuse_estimator: bool = False):
        s = settings or load_settings()
        pe = s.get("pose_estimator", {})
        tr = s.get("tracker", {})
        sc = s.get("scoring", {})
        ac = app_config or {}

        self.pass_accuracy = float(ac.get("passAccuracy", sc.get("pass_accuracy", 85.0)))
        if reuse_estimator and not static_image_mode:
            # 앱(키오스크)에서는 세션마다 모델을 다시 로드하지 않는다
            from .warm import get_estimator
            self.estimator = get_estimator(
                num_poses=pe.get("num_poses", 1),
                min_detection_confidence=pe.get("min_detection_confidence", 0.5),
                min_tracking_confidence=pe.get("min_tracking_confidence", 0.5),
            )
            self._owns_estimator = False
        else:
            self.estimator = MediaPipeEstimator(
                num_poses=pe.get("num_poses", 1),
                min_detection_confidence=pe.get("min_detection_confidence", 0.5),
                min_tracking_confidence=pe.get("min_tracking_confidence", 0.5),
                static_image_mode=static_image_mode,
            )
            self._owns_estimator = True
        self.tracker = PrimarySubjectTracker(
            center_weight=tr.get("center_weight", 0.3),
            min_iou_keep=tr.get("min_iou_keep", 0.2),
            grace_frames=tr.get("grace_frames", 15),
        )
        self.scorer = PoseScorer(
            min_keypoint_confidence=sc.get("min_keypoint_confidence", 0.4)
        )
        self.session = Session(
            pose_names, scorer=self.scorer, pass_accuracy=self.pass_accuracy,
            countdown_seconds=float(ac.get("countdownSeconds", 3.0)),
            result_seconds=float(ac.get("resultSeconds", 3.0)),
        )
        # 유지시간 오버라이드
        hold_override = ac.get("holdSecondsOverride")
        if hold_override is not None:
            for d in self.session.pose_defs:
                d.hold_seconds = float(hold_override)

    def process(self, frame, now: float) -> tuple[PersonPose | None, SessionState]:
        poses = self.estimator.estimate(frame)
        primary = self.tracker.update(poses)
        state = self.session.update(primary, now)
        return primary, state

    def close(self) -> None:
        if self._owns_estimator:
            self.estimator.close()
