"""2인 대결 화면: numPoses=2 추정 → 좌우 배정 → VersusSession → 분할 HUD."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.frame_source import FrameSource
from core.mediapipe_estimator import MediaPipeEstimator
from core.pose_def import load_pose
from core.scorer import PoseScorer
from core.sound import Sound
from core.versus import VersusSession, VState, assign_players
from ui.qtutil import bgr_to_qpixmap
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

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._estimator: MediaPipeEstimator | None = None
        self._source: FrameSource | None = None
        self._vs: VersusSession | None = None
        self._sound: Sound | None = None
        self._pass = 85.0
        self._start = 0.0
        self._prev = ""

    def begin(self, app_config: dict, source: FrameSource) -> None:
        self.stop()
        defs = [load_pose(n) for n in app_config["poseSet"]]
        ho = app_config.get("holdSecondsOverride")
        if ho is not None:
            for d in defs:
                d.hold_seconds = float(ho)
        self._pass = float(app_config.get("passAccuracy", 85.0))
        self._estimator = MediaPipeEstimator(num_poses=2)
        self._vs = VersusSession(defs, PoseScorer(), self._pass,
                                 float(app_config.get("countdownSeconds", 3.0)))
        self._sound = Sound(app_config.get("sound", True), app_config.get("voice", True))
        self._source = source
        self._start = time.monotonic()
        self._prev = ""
        self._home.hide()
        self._timer.start(33)

    def stop(self) -> None:
        self._timer.stop()
        if self._source is not None:
            self._source.release()
            self._source = None
        if self._estimator is not None:
            self._estimator.close()
            self._estimator = None

    def _exit(self) -> None:
        self.stop()
        self.exitRequested.emit()

    def _tick(self) -> None:
        if self._estimator is None or self._source is None or self._vs is None:
            return
        frame = self._source.read()
        if frame is None:
            if not self._source.is_open():
                self._timer.stop()
            return
        now = time.monotonic() - self._start
        poses = self._estimator.estimate(frame)
        a, b = assign_players(poses)
        state = self._vs.update(poses, now)
        composed = compose_versus(frame, a, b, state, self._pass)
        self._label.setPixmap(bgr_to_qpixmap(composed).scaled(
            self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self._cue(state)
        if state.state == VState.DONE:
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
        self._quit.setFixedSize(56, 44)
        self._quit.move(self.width() - 72, 16)
        self._home.adjustSize()
        self._home.move((self.width() - self._home.width()) // 2, int(self.height() * 0.9))
        super().resizeEvent(e)

    def render_once(self) -> None:
        self._tick()
