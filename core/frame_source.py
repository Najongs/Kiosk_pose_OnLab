"""입력 소스 추상화.

카메라가 아직 없으므로 이미지/영상 파일로 개발하고, 카메라가 생기면
CameraSource 로 교체만 하면 상위 로직은 그대로 동작한다.

모든 소스는 read() 로 (BGR ndarray) 프레임을 반환하고, 끝나면 None 을 반환한다.
"""

from __future__ import annotations

import glob
import os
from abc import ABC, abstractmethod

import cv2
import numpy as np

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def imread_unicode(path: str) -> "np.ndarray | None":
    """유니코드(한글) 경로 안전 이미지 읽기. Windows 의 cv2.imread 는 비ASCII
    경로에서 None 을 반환하므로 np.fromfile + imdecode 로 우회한다."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


class FrameSource(ABC):
    @abstractmethod
    def read(self) -> np.ndarray | None:
        """다음 프레임(BGR)을 반환. 더 없으면 None."""

    def is_open(self) -> bool:
        return True

    def release(self) -> None:
        pass

    def __iter__(self):
        return self

    def __next__(self) -> np.ndarray:
        frame = self.read()
        if frame is None:
            raise StopIteration
        return frame


class ImageSource(FrameSource):
    """단일 이미지 파일, 또는 폴더 안 모든 이미지를 순차 제공."""

    def __init__(self, path: str, loop: bool = False):
        if os.path.isdir(path):
            files: list[str] = []
            for ext in IMAGE_EXTS:
                files.extend(glob.glob(os.path.join(path, f"*{ext}")))
                files.extend(glob.glob(os.path.join(path, f"*{ext.upper()}")))
            self._paths = sorted(set(files))
        else:
            self._paths = [path]
        if not self._paths:
            raise FileNotFoundError(f"이미지를 찾을 수 없음: {path}")
        self._idx = 0
        self._loop = loop  # True 면 마지막 이후 처음으로 돌아감(앱 구동 테스트용)
        self.last_path: str | None = None

    def read(self) -> np.ndarray | None:
        if self._idx >= len(self._paths):
            if not self._loop:
                return None
            self._idx = 0
        path = self._paths[self._idx]
        self._idx += 1
        frame = imread_unicode(path)
        if frame is None:
            # 손상/미지원 파일은 건너뛴다
            self.last_path = path
            return self.read()
        self.last_path = path
        return frame

    def is_open(self) -> bool:
        return self._loop or self._idx < len(self._paths)


class VideoFileSource(FrameSource):
    """영상 파일(mp4 등)에서 프레임을 순차 제공."""

    def __init__(self, path: str):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"영상 파일 없음: {path}")
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise RuntimeError(f"영상을 열 수 없음: {path}")
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def is_open(self) -> bool:
        return self._cap.isOpened()

    def release(self) -> None:
        self._cap.release()


class CameraSource(FrameSource):
    """웹캠/키오스크 카메라. 카메라가 준비되면 사용."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720, fps: int = 30):
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"카메라를 열 수 없음: index={index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def is_open(self) -> bool:
        return self._cap.isOpened()

    def release(self) -> None:
        self._cap.release()


def open_source(path: str) -> FrameSource:
    """경로를 보고 적절한 소스를 자동 선택 (이미지/폴더 vs 영상)."""
    if os.path.isdir(path):
        return ImageSource(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return ImageSource(path)
    return VideoFileSource(path)
