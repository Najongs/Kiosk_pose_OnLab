"""세션 화면: 카메라 루프 + 스켈레톤/HUD/가이드 + 사운드 + 리더보드 기록."""

from __future__ import annotations

import datetime
import time

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.engine import Engine
from core.frame_source import FrameSource
from core.leaderboard import add_record
from core.refs import get_ref
from core.session import SessionState, State
from core.sound import Sound
from ui.frame_worker import FrameWorker
from ui.qtutil import bgr_to_qpixmap
from ui.renderer import compose


class SessionView(QWidget):
    exitRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#05070d;")
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._home_btn = QPushButton("홈으로", self)
        self._home_btn.clicked.connect(self._exit)
        self._home_btn.hide()
        self._quit_btn = QPushButton("✕", self)
        self._quit_btn.clicked.connect(self._exit)

        self._engine: Engine | None = None
        self._source: FrameSource | None = None
        self._sound: Sound | None = None
        self._thread: QThread | None = None
        self._worker: FrameWorker | None = None
        self._name = ""
        self._start = 0.0
        self._saved = False
        self._pass = 85.0
        self._reset_cue()

    # ---- 생명주기 ----
    def begin(self, name: str, app_config: dict, source: FrameSource) -> None:
        self.stop()
        self._name = name
        self._app_config = app_config
        self._engine = None  # 무거운 모델 로드는 워커 스레드에서 지연 생성
        self._pass = float(app_config.get("passAccuracy", 85.0))
        self._sound = Sound(app_config.get("sound", True), app_config.get("voice", True))
        self._source = source
        self._start = time.monotonic()
        self._saved = False
        self._reset_cue()
        self._home_btn.hide()
        self._label.setText("카메라·모델 준비 중…")
        self._label.setStyleSheet("color:#eef2fb; font-size:30px; background:#05070d;")
        self._start_worker(source)

    def _start_worker(self, source: FrameSource) -> None:
        self._thread = QThread(self)
        self._worker = FrameWorker(source, self._process)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_ready)   # 메인 스레드(큐)
        self._worker.stopped.connect(self._thread.quit)
        self._thread.start()

    def _process(self, frame):
        """워커 스레드에서 실행: 추론+합성(무거운 작업). GUI 객체 생성 금지.
        MediaPipe 엔진은 여기서(워커 스레드) 지연 생성 → 생성+사용 스레드 일치."""
        if self._engine is None:
            self._engine = Engine(self._app_config["poseSet"], app_config=self._app_config)
        primary, state = self._engine.process(frame, self._now())
        ref = get_ref(state.target_pose.name) if state.target_pose else None
        composed = compose(frame, primary, state, self._pass, ref)
        return composed, state

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._worker = None
        if self._source is not None:
            self._source.release()
            self._source = None
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    def _exit(self) -> None:
        self.stop()
        self.exitRequested.emit()

    def _now(self) -> float:
        return time.monotonic() - self._start

    # ---- 결과 수신(메인 스레드): 표시 + 사운드 + 기록 ----
    @Slot(object, object)
    def _on_ready(self, composed, state: SessionState) -> None:
        self._label.setPixmap(
            bgr_to_qpixmap(composed).scaled(
                self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        )
        self._cue(state)
        if state.state == State.DONE and not self._saved:
            self._saved = True
            add_record(self._name, state.final_summary or 0.0, state.results,
                       datetime.datetime.now().isoformat())
            self._home_btn.show()

    # ---- 사운드/음성 큐 (상태 전이 1회성) ----
    def _reset_cue(self) -> None:
        self._prev_state = ""
        self._prev_index = -1
        self._prev_count = -1

    def _cue(self, s: SessionState) -> None:
        if self._sound is None:
            return
        entered = s.state.value != self._prev_state or s.pose_index != self._prev_index
        if s.state == State.COUNTDOWN:
            if entered and s.target_pose:
                self._sound.speak(f"{s.target_pose.display_name} 준비")
            import math
            c = int(math.ceil(s.countdown_remaining or 0))
            if c != self._prev_count and c > 0:
                self._sound.tick()
            self._prev_count = c
        elif s.state == State.SCORING:
            if entered:
                self._sound.go()
            self._prev_count = -1
        elif s.state == State.RESULT:
            if entered:
                self._sound.success()
                self._sound.speak(f"완료! {round(s.last_score or 0)}점")
        elif s.state == State.DONE:
            if entered:
                self._sound.fanfare()
                self._sound.speak(f"전체 완료! 평균 {round(s.final_summary or 0)}점")
        self._prev_state = s.state.value
        self._prev_index = s.pose_index

    # ---- 레이아웃 ----
    def resizeEvent(self, e) -> None:
        self._label.setGeometry(0, 0, self.width(), self.height())
        self._quit_btn.setFixedSize(56, 44)
        self._quit_btn.move(self.width() - 72, 16)
        self._home_btn.adjustSize()
        self._home_btn.move((self.width() - self._home_btn.width()) // 2,
                            int(self.height() * 0.9))
        super().resizeEvent(e)

    def render_once(self):
        """헤드리스 검증용: 워커 없이 한 프레임 동기 처리."""
        if self._engine is None or self._source is None:
            return
        frame = self._source.read()
        if frame is None:
            return
        composed, state = self._process(frame)
        self._on_ready(composed, state)
