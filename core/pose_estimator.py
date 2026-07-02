"""포즈 추정 추상화.

상위 로직(추적/스코어링/UI)이 특정 모델(MediaPipe, YOLO-pose, RTMPose)에
의존하지 않도록 공통 인터페이스와 데이터 구조를 정의한다.

내부 키포인트 표준은 MediaPipe Pose의 33개 랜드마크 레이아웃을 채택한다.
(현재 기본 백엔드가 MediaPipe이고 33점이 17점보다 풍부하기 때문.)
추후 YOLO/RTMPose(COCO-17) 백엔드는 자신의 17점을 아래 인덱스에 매핑하고,
없는 관절은 낮은 visibility로 채우면 된다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


# --- MediaPipe Pose 33-landmark 인덱스 (내부 표준) ---
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

NUM_KEYPOINTS = 33

# 이름 → 인덱스 (JSON 자세 정의에서 관절을 이름으로 지정할 때 사용)
KEYPOINT_NAMES: dict[str, int] = {
    "nose": NOSE,
    "left_shoulder": LEFT_SHOULDER,
    "right_shoulder": RIGHT_SHOULDER,
    "left_elbow": LEFT_ELBOW,
    "right_elbow": RIGHT_ELBOW,
    "left_wrist": LEFT_WRIST,
    "right_wrist": RIGHT_WRIST,
    "left_hip": LEFT_HIP,
    "right_hip": RIGHT_HIP,
    "left_knee": LEFT_KNEE,
    "right_knee": RIGHT_KNEE,
    "left_ankle": LEFT_ANKLE,
    "right_ankle": RIGHT_ANKLE,
    "left_heel": LEFT_HEEL,
    "right_heel": RIGHT_HEEL,
    "left_foot_index": LEFT_FOOT_INDEX,
    "right_foot_index": RIGHT_FOOT_INDEX,
}

# 골격 연결선 (오버레이 그리기용)
SKELETON_EDGES: list[tuple[int, int]] = [
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_SHOULDER, LEFT_ELBOW),
    (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW),
    (RIGHT_ELBOW, RIGHT_WRIST),
    (LEFT_SHOULDER, LEFT_HIP),
    (RIGHT_SHOULDER, RIGHT_HIP),
    (LEFT_HIP, RIGHT_HIP),
    (LEFT_HIP, LEFT_KNEE),
    (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE),
    (RIGHT_KNEE, RIGHT_ANKLE),
    (LEFT_ANKLE, LEFT_FOOT_INDEX),
    (RIGHT_ANKLE, RIGHT_FOOT_INDEX),
]


@dataclass
class PersonPose:
    """한 사람의 포즈.

    keypoints: (33, 3) 배열. 각 행 = (x, y, visibility).
        x, y 는 이미지 픽셀 좌표. visibility 는 [0,1] 신뢰도.
    world_landmarks: (33, 3) 또는 None. 미터 단위 3D 좌표(원점=엉덩이 중앙).
        각도 계산에 더 견고하므로 있으면 우선 사용.
    bbox: (x1, y1, x2, y2) 픽셀 바운딩 박스.
    track_id: 추적기에서 부여하는 식별자(추정 단계에선 None).
    """

    keypoints: np.ndarray
    bbox: tuple[float, float, float, float]
    world_landmarks: np.ndarray | None = None
    track_id: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def bbox_area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @property
    def bbox_center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class PoseEstimator(ABC):
    """포즈 추정 백엔드 공통 인터페이스."""

    @abstractmethod
    def estimate(self, frame_bgr: np.ndarray) -> list[PersonPose]:
        """BGR 이미지 한 장에서 사람들의 포즈를 추정해 리스트로 반환."""

    def close(self) -> None:  # 선택적 정리 훅
        pass

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
