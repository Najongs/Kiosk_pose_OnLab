"""2인 대결 화면: numPoses=2 추정 → 좌우 배정 → VersusSession → 분할 HUD.

세션 화면과 동일한 성능 원칙: 무거운 작업(카메라 열기·모델·추론·합성·리사이즈)은
전부 워커 스레드, 모델은 core.warm 으로 재사용, 세션별 상태는 클로저 소유.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.pose_def import load_pose
from core.scorer import PoseScorer
from core.sound import Sound
from core.versus import VersusSession, VState, assign_players
from core.warm import get_estimator
from ui.frame_worker import FrameWorker
from ui.qtutil import bgr_to_qpixmap, fit_frame
from ui.renderer import compose_versus


class VersusView(QWidget):
    exitRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#05070d;")
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quit = QPushButton("✕", self)
        self._quit.clicked.connect(self._exit)
        self._home = QPushButton("홈으로", self)
        self._home.clicked.connect(self._exit)
        self._home.hide()

        self._source = None  # 헤드리스 render_once 용
        self._process_fn = None
        self._vs: VersusSession | None = None  # 검증 도구 호환용 참조
        self._sound: Sound | None = None
        self._sound_key: tuple | None = None
        self._thread: QThread | None = None
        self._worker: FrameWorker | None = None
        self._view_size: tuple[int, int] = (0, 0)
        self._pass = 85.0
        self._start = 0.0
        self._prev = ""

    def begin(self, app_config: dict, source) -> None:
        """source: FrameSource 인스턴스(헤드리스 검증) 또는 팩토리(callable)."""
        self.stop()
        self._pass = float(app_config.get("passAccuracy", 85.0))
        key = (bool(app_config.get("sound", True)), bool(app_config.get("voice", True)))
        if self._sound is None or self._sound_key != key:
            self._sound = Sound(*key)
            self._sound_key = key
        self._start = time.monotonic()
        self._prev = ""
        self._home.hide()
        self._label.setText("카메라·모델 준비 중… (2인)")
        self._label.setStyleSheet("color:#eef2fb; font-size:30px; background:#05070d;")

        cfg = app_config
        pass_acc = self._pass
        start = self._start
        holder: dict = {}

        def process(frame):
            """워커 스레드 전용: 자세 로드·2인 모델·대결 상태를 이 세션이 소유."""
            ctx = holder.get("ctx")
            if ctx is None:
                defs = [load_pose(n) for n in cfg["poseSet"]]
                ho = cfg.get("holdSecondsOverride")
                if ho is not None:
                    for d in defs:
                        d.hold_seconds = float(ho)
                est = get_estimator(num_poses=2)
                vs = VersusSession(defs, PoseScorer(), pass_acc,
                                   float(cfg.get("countdownSeconds", 3.0)))
                ctx = (est, vs)
                holder["ctx"] = ctx
                self._vs = vs
            est, vs = ctx
            now = time.monotonic() - start
            poses = est.estimate(frame)
            a, b = assign_players(poses)
            state = vs.update(poses, now)
            composed = compose_versus(frame, a, b, state, pass_acc)
            return fit_frame(composed, self._view_size), state

        self._process_fn = process
        if not callable(source):
            self._source = source
        self._thread = QThread(self)
        self._worker = FrameWorker(source, process)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.stopped.connect(self._thread.quit)
        self._thread.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            for sig, slot in ((self._worker.ready, self._on_ready),
                              (self._worker.failed, self._on_failed)):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        if self._thread is not None:
            self._thread.quit()
            if self._thread.wait(500):
                self._thread.deleteLater()
            else:
                self._thread.finished.connect(self._thread.deleteLater)
            self._thread = None
            self._worker = None
        if self._source is not None:
            try:
                self._source.release()
            except Exception:
                pass
            self._source = None
        self._vs = None  # 공유 모델은 core.warm 이 관리 — close 하지 않음

    def _exit(self) -> None:
        self.stop()
        self.exitRequested.emit()

    @Slot(object, object)
    def _on_ready(self, composed, state) -> None:
        pix = bgr_to_qpixmap(composed)
        if pix.width() > self._label.width() or pix.height() > self._label.height():
            pix = pix.scaled(self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        self._label.setPixmap(pix)
        self._cue(state)
        if state.state == VState.DONE:
            self._home.show()

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._label.setText(f"시작/처리 실패: {msg}")
        self._home.show()

    def _cue(self, state) -> None:
        if self._sound is None:
            return
        if state.state.value != self._prev:
            if state.state == VState.PLAYING:
                self._sound.go()
            elif state.state == VState.DONE:
                self._sound.fanfare()
                self._sound.speak(state.message)
            self._prev = state.state.value

    def resizeEvent(self, e) -> None:
        self._label.setGeometry(0, 0, self.width(), self.height())
        self._view_size = (self.width(), self.height())
        self._quit.setFixedSize(56, 44)
        self._quit.move(self.width() - 72, 16)
        self._home.adjustSize()
        self._home.move((self.width() - self._home.width()) // 2, int(self.height() * 0.9))
        super().resizeEvent(e)

    def render_once(self) -> None:
        if self._process_fn is None or self._source is None:
            return
        frame = self._source.read()
        if frame is None:
            return
        composed, state = self._process_fn(frame)
        self._on_ready(composed, state)
