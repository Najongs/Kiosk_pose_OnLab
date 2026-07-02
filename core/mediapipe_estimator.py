"""MediaPipe Pose Landmarker(Tasks API) 기반 PoseEstimator 구현.

설치된 mediapipe(0.10.x, Tasks 전용 빌드)는 레거시 mp.solutions 대신
mediapipe.tasks 의 PoseLandmarker 를 제공한다. Tasks API 는 num_poses 로
다중 인물 검출을 지원하므로, 군중 속에서 여러 명을 검출한 뒤 tracker 가
주 대상을 고르는 구조에 더 적합하다.

모델 번들(.task)이 필요하다: models/pose_landmarker_full.task
(다운로드: https://storage.googleapis.com/mediapipe-models/pose_landmarker/...)

world_landmarks(미터 단위 3D)도 함께 반환해 각도 계산을 견고하게 한다.
"""

from __future__ import annotations

import os

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .pose_estimator import NUM_KEYPOINTS, PersonPose, PoseEstimator

_DEFAULT_MODEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "pose_landmarker_full.task",
)


class MediaPipeEstimator(PoseEstimator):
    def __init__(
        self,
        model_path: str | None = None,
        num_poses: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        static_image_mode: bool = False,
    ):
        model_path = model_path or _DEFAULT_MODEL
        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"PoseLandmarker 모델을 찾을 수 없음: {model_path}\n"
                "models/ 폴더에 pose_landmarker_full.task 를 받아두세요."
            )

        self._image_mode = static_image_mode
        running_mode = (
            vision.RunningMode.IMAGE if static_image_mode else vision.RunningMode.VIDEO
        )
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=running_mode,
            num_poses=num_poses,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._ts_ms = 0  # VIDEO 모드용 단조 증가 타임스탬프

    def estimate(self, frame_bgr: np.ndarray) -> list[PersonPose]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        if self._image_mode:
            result = self._landmarker.detect(mp_image)
        else:
            self._ts_ms += 33  # ~30fps 가정 (정확한 fps 없이도 단조 증가면 충분)
            result = self._landmarker.detect_for_video(mp_image, self._ts_ms)

        if not result.pose_landmarks:
            return []

        world_list = result.pose_world_landmarks or []
        out: list[PersonPose] = []
        for pi, landmarks in enumerate(result.pose_landmarks):
            kps = np.zeros((NUM_KEYPOINTS, 3), dtype=np.float32)
            for i, lm in enumerate(landmarks):
                if i >= NUM_KEYPOINTS:
                    break
                kps[i, 0] = lm.x * w
                kps[i, 1] = lm.y * h
                # Tasks API 는 visibility/presence 를 제공 (없으면 1.0)
                kps[i, 2] = getattr(lm, "visibility", 1.0)

            world = None
            if pi < len(world_list):
                world = np.zeros((NUM_KEYPOINTS, 3), dtype=np.float32)
                for i, lm in enumerate(world_list[pi]):
                    if i >= NUM_KEYPOINTS:
                        break
                    world[i] = (lm.x, lm.y, lm.z)

            bbox = self._bbox_from_keypoints(kps, w, h)
            out.append(PersonPose(keypoints=kps, bbox=bbox, world_landmarks=world))
        return out

    @staticmethod
    def _bbox_from_keypoints(
        kps: np.ndarray, w: int, h: int, vis_thresh: float = 0.3
    ) -> tuple[float, float, float, float]:
        visible = kps[kps[:, 2] >= vis_thresh]
        if len(visible) == 0:
            visible = kps
        x1 = float(np.clip(visible[:, 0].min(), 0, w))
        y1 = float(np.clip(visible[:, 1].min(), 0, h))
        x2 = float(np.clip(visible[:, 0].max(), 0, w))
        y2 = float(np.clip(visible[:, 1].max(), 0, h))
        return (x1, y1, x2, y2)

    def close(self) -> None:
        self._landmarker.close()
