"""세션 화면: 카메라 루프 + 스켈레톤/HUD/가이드 + 사운드 + 리더보드 기록.

성능 원칙:
- 카메라 열기·모델 로드·추론·합성·리사이즈는 전부 워커 스레드(FrameWorker).
- 모델은 core.warm 으로 앱 수명 동안 재사용(세션마다 재로딩 없음).
- UI 스레드는 완성된 프레임을 QPixmap 으로 바꿔 표시만 한다.
- 세션별 가변 상태(엔진 등)는 begin() 의 클로저가 소유 — 이전 워커가 아직
  종료 중이어도 새 세션과 상태를 공유하지 않는다.
"""

from __future__ import annotations

import collections
import datetime
import time

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.engine import Engine
from core.leaderboard import add_record
from core.refs import get_ref
from core.session import SessionState, State
from core.sound import Sound
from ui.frame_worker import FrameWorker
from ui.qtutil import bgr_to_qpixmap, draw_fps, fit_frame
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
        self._skip_btn = QPushButton("건너뛰기 ▶", self)
        self._skip_btn.clicked.connect(self._on_skip)
        self._skip_btn.hide()
        self._request_skip = None  # begin() 이 세션 클로저의 skip 플래그 setter 를 넣음

        self._engine: Engine | None = None  # 검증 도구 호환용 참조(워커가 생성)
        self._source = None                  # 헤드리스 render_once 용
        self._infer_fn = None
        self._render_fn = None
        self._sound: Sound | None = None
        self._sound_key: tuple | None = None
        self._thread: QThread | None = None
        self._worker: FrameWorker | None = None
        self._view_size: tuple[int, int] = (0, 0)
        self._name = ""
        self._start = 0.0
        self._saved = False
        self._pass = 85.0
        self._reset_cue()

    # ---- 생명주기 ----
    def begin(self, name: str, app_config: dict, source) -> None:
        """source: FrameSource 인스턴스(헤드리스 검증) 또는 팩토리(callable).
        팩토리면 워커 스레드에서 열어 UI 가 멈추지 않는다."""
        self.stop()
        self._name = name
        self._pass = float(app_config.get("passAccuracy", 85.0))
        key = (bool(app_config.get("sound", True)), bool(app_config.get("voice", True)))
        if self._sound is None or self._sound_key != key:
            self._sound = Sound(*key)
            self._sound_key = key
        self._start = time.monotonic()
        self._saved = False
        self._reset_cue()
        self._home_btn.hide()
        self._label.setText("카메라·모델 준비 중…")
        self._label.setStyleSheet("color:#eef2fb; font-size:30px; background:#05070d;")

        cfg = app_config
        pass_acc = self._pass
        start = self._start
        show_fps = bool(app_config.get("showFps", False))
        disp_ts: collections.deque = collections.deque(maxlen=40)
        infer_ts: collections.deque = collections.deque(maxlen=20)
        holder: dict = {}
        flags = {"skip": False}  # UI 스레드가 세우고 표시 루프가 소비

        def infer(frame):
            """추론 스레드 전용(무거움): 모델 로드 + 포즈 추정 + 주 대상 추적."""
            eng = holder.get("engine")
            if eng is None:
                eng = Engine(cfg["poseSet"], app_config=cfg, reuse_estimator=True)
                holder["engine"] = eng
                self._engine = eng
            poses = eng.estimator.estimate(frame)
            if show_fps:
                infer_ts.append(time.monotonic())
            return eng.tracker.update(poses)

        def render(frame, primary):
            """표시 루프(카메라 fps): 마지막 추론 결과로 상태 갱신 + 합성."""
            eng = holder.get("engine")
            if eng is None:
                # 모델 로딩 중 — 카메라 미리보기만 먼저 보여준다
                return fit_frame(frame, self._view_size), None
            now = time.monotonic() - start
            if flags["skip"]:
                flags["skip"] = False
                eng.session.skip(now)
            state = eng.session.update(primary, now)
            ref = get_ref(state.target_pose.name) if state.target_pose else None
            composed = compose(frame, primary, state, pass_acc, ref, anim_t=now)
            if show_fps:
                disp_ts.append(time.monotonic())
                draw_fps(composed, disp_ts, infer_ts)
            return fit_frame(composed, self._view_size), state

        self._infer_fn = infer
        self._render_fn = render
        self._request_skip = lambda: flags.__setitem__("skip", True)
        self._skip_btn.show()
        if not callable(source):
            self._source = source
        self._start_worker(source, infer, render)

    def _start_worker(self, source, infer_fn, render_fn) -> None:
        self._thread = QThread(self)
        self._worker = FrameWorker(source, infer_fn, render_fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_ready)   # 메인 스레드(큐)
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
                # 추론 중인 프레임이 끝나면 워커가 소스를 해제하고 스스로 종료한다.
                # UI 스레드는 기다리지 않는다(응답없음 방지).
                self._thread.finished.connect(self._thread.deleteLater)
            self._thread = None
            self._worker = None
        if self._source is not None:  # 직접 받은 소스(헤드리스)만 여기서 해제
            try:
                self._source.release()
            except Exception:
                pass
            self._source = None
        self._engine = None  # 공유 모델은 core.warm 이 관리 — close 하지 않음
        self._request_skip = None
        self._skip_btn.hide()

    def _exit(self) -> None:
        self.stop()
        self.exitRequested.emit()

    # ---- 결과 수신(메인 스레드): 표시 + 사운드 + 기록 ----
    @Slot(object, object)
    def _on_ready(self, composed, state: SessionState | None) -> None:
        pix = bgr_to_qpixmap(composed)
        if pix.width() > self._label.width() or pix.height() > self._label.height():
            pix = pix.scaled(self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        self._label.setPixmap(pix)
        if state is None:  # 모델 로딩 중 미리보기 프레임
            return
        self._cue(state)
        if state.state == State.DONE and not self._saved:
            self._saved = True
            add_record(self._name, state.final_summary or 0.0, state.results,
                       datetime.datetime.now().isoformat())
            self._home_btn.show()
            self._skip_btn.hide()

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._label.setText(f"시작/처리 실패: {msg}")
        self._home_btn.show()
        self._skip_btn.hide()

    def _on_skip(self) -> None:
        if self._request_skip is not None:
            self._request_skip()

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
        self._view_size = (self.width(), self.height())  # 워커가 읽는 리사이즈 목표
        self._quit_btn.setFixedSize(56, 44)
        self._quit_btn.move(self.width() - 72, 16)
        self._home_btn.adjustSize()
        self._home_btn.move((self.width() - self._home_btn.width()) // 2,
                            int(self.height() * 0.9))
        self._skip_btn.adjustSize()
        self._skip_btn.move(self.width() - self._skip_btn.width() - 24,
                            int(self.height() * 0.88))
        super().resizeEvent(e)

    def render_once(self):
        """헤드리스 검증용: 워커 없이 한 프레임 동기 처리(추론+합성)."""
        if self._infer_fn is None or self._source is None:
            return
        frame = self._source.read()
        if frame is None:
            return
        primary = self._infer_fn(frame.copy())
        composed, state = self._render_fn(frame, primary)
        self._on_ready(composed, state)
