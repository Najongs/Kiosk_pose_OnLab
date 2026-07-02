"""백그라운드 프레임 워커 — 표시와 추론을 분리한 2단 파이프라인.

화면 fps 가 추론 속도에 묶이지 않게 한다:
- 표시 루프(워커 스레드): 카메라에서 프레임을 읽는 즉시, "마지막 추론 결과"를
  얹어 합성/emit → 카메라 fps(30) 그대로 부드럽게 표시.
- 추론 루프(내부 스레드): 항상 최신 프레임 하나만 골라 포즈 추정 → 결과 갱신.
  추론이 느려도 화면은 안 끊기고, 스켈레톤만 추론 주기로 갱신된다.

source 로 FrameSource 인스턴스 대신 팩토리(callable)를 주면 워커 스레드에서
연다 — Windows 에서 카메라 열기(cv2.VideoCapture)가 수 초 걸려도 UI 가 멈추지
않는다. 워커가 연/받은 소스는 종료 시 워커가 release 한다.

주의: QPixmap 등 GUI 객체는 워커 스레드에서 만들면 안 된다. 여기서는 numpy
프레임만 만들어 emit 하고, QPixmap 변환은 수신 측(메인 스레드)에서 한다.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


class FrameWorker(QObject):
    # (composed_bgr: np.ndarray, state: object | None)
    ready = Signal(object, object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, source, infer_fn: Callable, render_fn: Callable,
                 max_fps: float = 30.0):
        """infer_fn(frame) -> 추론 결과(무거움, 내부 스레드에서 실행).
        render_fn(frame, 최신 추론 결과 | None) -> (합성 프레임, 상태 | None)."""
        super().__init__()
        self._source_or_factory = source
        self._infer = infer_fn
        self._render = render_fn
        self._min_dt = 1.0 / max_fps if max_fps > 0 else 0.0
        self._running = False
        self._latest: tuple[int, object] | None = None  # (seq, frame 복사본)
        self._seq = 0
        self._out = None            # 마지막 추론 결과
        self._infer_error: str | None = None

    @Slot()
    def run(self) -> None:
        self._running = True
        src = self._source_or_factory
        try:
            source = src() if callable(src) else src
        except Exception as e:
            self._running = False
            self.failed.emit(str(e))
            self.stopped.emit()
            return
        infer_thread = threading.Thread(target=self._infer_loop,
                                        name="pose-infer", daemon=True)
        infer_thread.start()
        last_emit = 0.0
        no_frame_since: float | None = None
        try:
            while self._running:
                frame = source.read()
                if frame is None:
                    if not source.is_open():
                        break
                    # 열려는 있는데 프레임이 계속 안 오면 무한 대기 대신 실패 처리
                    now = time.monotonic()
                    if no_frame_since is None:
                        no_frame_since = now
                    elif now - no_frame_since > 8.0:
                        self.failed.emit("카메라에서 프레임이 오지 않습니다 — "
                                         "연결 상태나 다른 앱의 카메라 사용 여부를 확인하세요")
                        break
                    QThread.msleep(5)
                    continue
                no_frame_since = None
                # 추론용 복사본(표시 루프가 원본에 오버레이를 그리므로)
                self._seq += 1
                self._latest = (self._seq, frame.copy())
                if self._infer_error:
                    self.failed.emit(self._infer_error)
                    break
                try:
                    composed, state = self._render(frame, self._out)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.failed.emit(f"{type(e).__name__}: {e}")
                    break
                if not self._running:
                    break
                self.ready.emit(composed, state)
                # 카메라는 read() 가 자체 페이싱하지만, 이미지/영상 소스는
                # 무한정 빨라질 수 있어 상한을 둔다.
                now = time.monotonic()
                wait = self._min_dt - (now - last_emit)
                if wait > 0.002:
                    QThread.msleep(int(wait * 1000))
                last_emit = time.monotonic()
        finally:
            self._running = False
            infer_thread.join(timeout=2.0)
            try:
                source.release()
            except Exception:
                pass
            self.stopped.emit()

    def _infer_loop(self) -> None:
        """내부 스레드: 항상 최신 프레임만 추론(밀린 프레임은 버림)."""
        done_seq = -1
        while self._running:
            item = self._latest
            if item is None or item[0] == done_seq:
                time.sleep(0.002)
                continue
            seq, frame = item
            try:
                self._out = self._infer(frame)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._infer_error = f"{type(e).__name__}: {e}"
                return
            done_seq = seq

    def stop(self) -> None:
        self._running = False
