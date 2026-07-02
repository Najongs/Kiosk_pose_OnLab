"""입력 소스 추상화.

카메라가 아직 없으므로 이미지/영상 파일로 개발하고, 카메라가 생기면
CameraSource 로 교체만 하면 상위 로직은 그대로 동작한다.

모든 소스는 read() 로 (BGR ndarray) 프레임을 반환하고, 끝나면 None 을 반환한다.
"""

from __future__ import annotations

import glob
import json
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


def _measure_fps(cap, n: int = 10, timeout: float = 2.0) -> float:
    """실전송 fps 측정. 드라이버가 보고하는 명목값(30)과 달리 무압축 고해상도는
    USB 대역폭 때문에 실제 전달이 7~10fps 인 경우가 많다."""
    for _ in range(3):  # 워밍업(자동 노출 안정)
        cap.read()
    t0 = time.monotonic()
    count = 0
    while count < n and time.monotonic() - t0 < timeout:
        ok, frame = cap.read()
        if ok and frame is not None:
            count += 1
    dt = time.monotonic() - t0
    return count / dt if dt > 0 else 0.0


def _open_msmf_guarded(index: int, width: int, height: int, fps: int,
                       timeout: float = 6.0):
    """MSMF 는 일부 환경에서 VideoCapture 열기 자체가 무한 블록된다.
    별도 스레드에서 열고 타임아웃을 걸어, 멈추면 포기한다(최후 수단 전용)."""
    import threading
    box: dict = {}

    def work():
        os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
        box["cap"] = _try_open(index, cv2.CAP_MSMF, width, height, fps)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        print("[카메라] MSMF 열기 응답 없음 — 건너뜀")
        return None
    return box.get("cap")


# 한 번 찾은 좋은 모드는 기억해 다음부터 스캔 없이 즉시 오픈.
# 프로세스 내 캐시 + 디스크(config/camera_cache.json, 앱 재시작에도 유지).
# 관리자 화면의 '카메라 재탐색' 으로만 초기화된다.
_MODE_CACHE: dict[int, tuple[int, int]] = {}
_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "camera_cache.json")


def _load_mode_cache(index: int) -> tuple[int, int] | None:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            d = json.load(f).get(str(index))
        if d:
            return int(d["width"]), int(d["height"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _save_mode_cache(index: int, mode: tuple[int, int]) -> None:
    try:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            m = {}
        m[str(index)] = {"width": mode[0], "height": mode[1]}
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def clear_camera_cache() -> None:
    """관리자 '카메라 재탐색': 다음 세션에서 최적 모드를 다시 측정한다."""
    _MODE_CACHE.clear()
    try:
        os.remove(_CACHE_PATH)
    except FileNotFoundError:
        pass


def _open_camera(index: int, width: int, height: int, fps: int,
                 min_fps: float = 15.0):
    """실측 fps 기반 자동 협상: 높은 해상도부터 실제 전송 fps 를 재서
    min_fps 이상 나오는 가장 선명한 모드를 채택한다.

    Windows 는 DSHOW 만 신뢰한다(MSMF 는 열기 자체가 무한 블록되는 환경이
    있어 최후 수단으로만, 타임아웃을 걸고 시도). 무압축(YUY2) 카메라는
    해상도에 따라 USB 대역폭이 실전송 fps 를 좌우한다:
    720p ≈ 7~10fps, 800x600 ≈ 15~20fps, 640x480 ≈ 30fps.
    """
    be = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

    cached = _MODE_CACHE.get(index) or _load_mode_cache(index)
    if cached:
        cap = _try_open(index, be, cached[0], cached[1], fps)
        if cap is not None and _probe(cap):
            _MODE_CACHE[index] = cached
            print(f"[카메라] 저장된 최적 모드 {cached[0]}x{cached[1]} 사용 "
                  "(재탐색: 관리자 → 카메라 재탐색)")
            return cap
        if cap is not None:
            cap.release()
        _MODE_CACHE.pop(index, None)  # 카메라가 바뀐 듯 — 아래에서 재스캔

    candidates = [(width, height)]
    for wh in ((1024, 576), (800, 600), (640, 480)):
        if wh not in candidates and wh[0] * wh[1] < width * height:
            candidates.append(wh)

    tested: set = set()
    best_mode: tuple[int, int] | None = None
    best_fps = -1.0
    for w, h in candidates:
        cap = _try_open(index, be, w, h, fps)
        if cap is None:
            continue
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (aw, ah) in tested:  # 드라이버가 같은 모드로 붙임 — 재측정 불필요
            cap.release()
            continue
        tested.add((aw, ah))
        if not _probe(cap):
            print(f"[카메라] {_backend_name(be)} {aw}x{ah}: 프레임 없음 — 다음 시도")
            cap.release()
            continue
        measured = _measure_fps(cap)
        codec = _codec_of(cap)
        if measured >= min_fps:
            print(f"[카메라] {_backend_name(be)} {aw}x{ah} {codec} "
                  f"실측 {measured:.1f}fps ≥ 최소 {min_fps:.0f} — 채택·저장")
            _MODE_CACHE[index] = (aw, ah)
            _save_mode_cache(index, (aw, ah))
            return cap
        print(f"[카메라] {_backend_name(be)} {aw}x{ah} {codec} "
              f"실측 {measured:.1f}fps < 최소 {min_fps:.0f} — 낮은 해상도 시도")
        if measured > best_fps:
            best_fps, best_mode = measured, (aw, ah)
        cap.release()  # 같은 장치라 다음 후보를 열려면 먼저 놓아줘야 함

    if best_mode is not None:  # 최소 fps 미달 — 가장 빨랐던 모드라도 사용
        cap = _try_open(index, be, best_mode[0], best_mode[1], fps)
        if cap is not None and _probe(cap):
            print(f"[카메라] 최소 fps 미달 — 가장 빠른 {best_mode[0]}x{best_mode[1]} "
                  f"({best_fps:.1f}fps) 사용·저장")
            _MODE_CACHE[index] = best_mode
            _save_mode_cache(index, best_mode)
            return cap
        if cap is not None:
            cap.release()

    if sys.platform == "win32":  # 최후 수단
        cap = _open_msmf_guarded(index, width, height, fps)
        if cap is not None:
            if _probe(cap):
                return cap
            cap.release()
    return None


class CameraSource(FrameSource):
    """웹캠/키오스크 카메라. 카메라가 준비되면 사용."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720,
                 fps: int = 30, min_fps: float = 15.0):
        cap = _open_camera(index, width, height, fps, min_fps)
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
