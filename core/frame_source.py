"""입력 소스 추상화.

카메라가 아직 없으므로 이미지/영상 파일로 개발하고, 카메라가 생기면
CameraSource 로 교체만 하면 상위 로직은 그대로 동작한다.

모든 소스는 read() 로 (BGR ndarray) 프레임을 반환하고, 끝나면 None 을 반환한다.
"""

from __future__ import annotations

import glob
import os
import sys
import time
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
        # 반복(loop) 재생 시 같은 파일을 매번 디코드하지 않도록 캐시.
        # 하위에서 프레임에 오버레이를 그리므로 복사본을 내보낸다.
        self._cache: dict[str, np.ndarray] = {}

    _CACHE_MAX = 32

    def read(self) -> np.ndarray | None:
        for _ in range(len(self._paths) + 1):
            if self._idx >= len(self._paths):
                if not self._loop:
                    return None
                self._idx = 0
            path = self._paths[self._idx]
            self._idx += 1
            self.last_path = path
            cached = self._cache.get(path)
            if cached is not None:
                return cached.copy()
            frame = imread_unicode(path)
            if frame is None:
                continue  # 손상/미지원 파일은 건너뛴다
            if self._loop and len(self._cache) < self._CACHE_MAX:
                self._cache[path] = frame.copy()
            return frame
        return None  # 읽을 수 있는 파일이 하나도 없음

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


def _codec_of(cap) -> str:
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    return "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4)).strip("\x00")


def _try_open(index: int, backend: int, width: int, height: int, fps: int):
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    # 일부 드라이버는 FOURCC 변경 후 크기를 다시 설정해야 반영된다
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 오래된 프레임이 쌓이지 않게
    return cap


_BE_NAME = {}


def _backend_name(be: int) -> str:
    if not _BE_NAME:
        _BE_NAME.update({cv2.CAP_MSMF: "MSMF", cv2.CAP_DSHOW: "DSHOW",
                         cv2.CAP_ANY: "AUTO"})
    return _BE_NAME.get(be, str(be))


def _probe(cap, tries: int = 25, delay: float = 0.06) -> bool:
    """isOpened() 만 믿지 말고 실제 프레임이 나오는지 확인 (최대 ~1.5초).
    일부 조합(백엔드×포맷)은 열리긴 해도 프레임을 전혀 주지 않는다."""
    for _ in range(tries):
        ok, frame = cap.read()
        if ok and frame is not None:
            return True
        time.sleep(delay)
    return False


def _open_camera(index: int, width: int, height: int, fps: int):
    """MJPG 30fps 를 목표로 백엔드/해상도를 자동 협상. 실제 프레임이 나오는
    조합만 채택한다.

    무압축(YUY2)은 720p 에서 USB 대역폭 때문에 실제 7~10fps 밖에 안 나온다.
    1) 각 백엔드에서 MJPG 협상 + 프레임 확인 (Windows: MSMF → DSHOW)
    2) 전부 YUY2 로만 열리면 640x480 으로 낮춰 대역폭 내 30fps 확보
       (포즈 모델은 내부에서 더 작게 줄여 쓰므로 정확도 영향 미미)
    """
    if sys.platform == "win32":
        # MSMF 가 열리는 데 수 초 걸리는 원인(HW 변환 초기화)을 끈다 — 오픈 즉시화
        os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
        backends = [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_ANY]

    def attempt(w: int, h: int, want_mjpg: bool):
        """(작동 확인된 cap, backend) 반환. want_mjpg=True 면 MJPG 협상만 채택."""
        for be in backends:
            cap = _try_open(index, be, w, h, fps)
            if cap is None:
                continue
            codec = _codec_of(cap)
            if want_mjpg and codec != "MJPG":
                cap.release()
                continue
            if _probe(cap):
                return cap, be
            print(f"[카메라] {_backend_name(be)} {w}x{h} {codec}: "
                  "열렸지만 프레임 없음 — 다음 조합 시도")
            cap.release()
        return None, None

    cap, _ = attempt(width, height, want_mjpg=True)      # 1) MJPG 원해상도
    if cap is not None:
        return cap
    if width > 640 or height > 480:                       # 2) 저해상도(대역폭 확보)
        cap, _ = attempt(640, 480, want_mjpg=False)
        if cap is not None:
            return cap
    cap, _ = attempt(width, height, want_mjpg=False)      # 3) 마지막: 되는 대로
    return cap


class CameraSource(FrameSource):
    """웹캠/키오스크 카메라. 카메라가 준비되면 사용."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720, fps: int = 30):
        cap = _open_camera(index, width, height, fps)
        if cap is None or not cap.isOpened():
            raise RuntimeError(f"카메라를 열 수 없음: index={index}")
        self._cap = cap
        # 실제 협상된 값 로그 — 요청과 다르면(YUY2/15fps 등) 카메라 한계 진단용
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        f = self._cap.get(cv2.CAP_PROP_FPS)
        print(f"[카메라] index={index} {w}x{h} @{f:.0f}fps codec={_codec_of(self._cap) or '?'} "
              f"(요청: {width}x{height} @{fps}fps MJPG)")

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
