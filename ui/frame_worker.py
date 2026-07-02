"""백그라운드 프레임 워커.

무거운 작업(카메라 열기 + 읽기 + 포즈 추정 + 화면 합성)을 UI 스레드가 아닌
별도 스레드에서 수행해 창이 "응답 없음"이 되지 않게 한다. 결과(합성 프레임
numpy + 상태 객체)만 시그널로 메인 스레드에 전달하고, 메인 스레드는
표시/사운드만 담당.

source 로 FrameSource 인스턴스 대신 팩토리(callable)를 주면 워커 스레드에서
연다 — Windows 에서 카메라 열기(cv2.VideoCapture)가 수 초 걸려도 UI 가 멈추지
않는다. 워커가 연/받은 소스는 종료 시 워커가 release 한다.

주의: QPixmap 등 GUI 객체는 워커 스레드에서 만들면 안 된다. 여기서는 numpy
프레임만 만들어 emit 하고, QPixmap 변환은 수신 측(메인 스레드)에서 한다.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


class FrameWorker(QObject):
    # (composed_bgr: np.ndarray, state: object)
    ready = Signal(object, object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, source, process_fn: Callable[[object], tuple]):
        super().__init__()
        self._source_or_factory = source
        self._process = process_fn
        self._running = False

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
        try:
            while self._running:
                frame = source.read()
                if frame is None:
                    if not source.is_open():
                        break
                    QThread.msleep(5)
                    continue
                try:
                    composed, state = self._process(frame)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.failed.emit(f"{type(e).__name__}: {e}")
                    break
                if not self._running:
                    break
                self.ready.emit(composed, state)
                QThread.msleep(1)  # 이벤트 처리 양보
        finally:
            self._running = False
            try:
                source.release()
            except Exception:
                pass
            self.stopped.emit()

    def stop(self) -> None:
        self._running = False
