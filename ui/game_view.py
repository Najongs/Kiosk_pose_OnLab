"""게임 뷰 공통 베이스 — 워커 스레드 수명주기 + 표시 + 종료/실패 처리.

SessionView/VersusView 에서 반복되던 보일러플레이트를 모은 것. 서브클래스는
build(cfg) 로 (infer, render) 클로저 쌍만 제공하면 된다:

  infer(frame) -> result          # 추론 스레드(무거움) — 모델은 core.warm 재사용
  render(frame, result) -> (composed_bgr, state_or_None)   # 표시 루프(카메라 fps)

성능 원칙은 session_view.py 와 동일: 카메라 열기·모델 로드·추론·합성은 전부
워커 스레드, UI 스레드는 QPixmap 표시만. 워커 스레드에서 Qt 객체 생성 금지.
"""

from __future__ import annotations

import datetime
import time

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from core.leaderboard import add_record
from core.sound import Sound
from ui.frame_worker import FrameWorker
from ui.qtutil import bgr_to_qpixmap


class BaseGameView(QWidget):
    exitRequested = Signal()

    game_id: str = "game"                    # 리더보드 기록 키
    loading_text: str = "카메라·모델 준비 중… · Getting ready"

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#05070d;")
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quit_btn = QPushButton("✕", self)
        self._quit_btn.clicked.connect(self._exit)
        self._home_btn = QPushButton("홈으로 · Home", self)
        self._home_btn.clicked.connect(self._exit)
        self._home_btn.hide()

        self._source = None            # 헤드리스 render_once 용 (직접 받은 소스)
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
        self._prev_state = ""

    # ---- 서브클래스 훅 ----
    def build(self, cfg: dict):
        """(infer, render) 클로저 쌍을 만든다. 게임별 상태(추정기·게임 객체)는
        클로저의 holder dict 가 소유할 것 — 이전 워커와 상태를 공유하지 않는다."""
        raise NotImplementedError

    def _handle_state(self, state) -> None:
        """상태 스냅샷 수신(메인 스레드) — 사운드 큐·기록 등. 기본 no-op."""

    def _on_stop(self) -> None:
        """stop() 마지막에 불리는 정리 훅. 기본 no-op."""

    # ---- 생명주기 ----
    def begin(self, app_config: dict, source, name: str = "") -> None:
        """source: FrameSource 인스턴스(헤드리스 검증) 또는 팩토리(callable).
        팩토리면 워커 스레드에서 열어 UI 가 멈추지 않는다."""
        self.stop()
        self._name = name
        self._setup_sound(app_config)
        self._start = time.monotonic()
        self._saved = False
        self._prev_state = ""
        self._home_btn.hide()
        self._label.setText(self.loading_text)
        self._label.setStyleSheet(
            "color:#eef2fb; font-size:30px; background:#05070d;")
        infer, render = self.build(app_config)
        self._infer_fn = infer
        self._render_fn = render
        if not callable(source):
            self._source = source
        self._start_worker(source, infer, render)

    def _setup_sound(self, cfg: dict) -> None:
        key = (bool(cfg.get("sound", True)), bool(cfg.get("voice", True)))
        if self._sound is None or self._sound_key != key:
            self._sound = Sound(*key)
            self._sound_key = key

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
        self._on_stop()

    def _exit(self) -> None:
        self.stop()
        self.exitRequested.emit()

    # ---- 결과 수신(메인 스레드) ----
    def _display(self, composed) -> tuple[int, int]:
        pix = bgr_to_qpixmap(composed)
        if pix.width() > self._label.width() or pix.height() > self._label.height():
            pix = pix.scaled(self._label.size(),
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        self._label.setPixmap(pix)
        return pix.width(), pix.height()

    @Slot(object, object)
    def _on_ready(self, composed, state) -> None:
        self._display(composed)
        if state is None:  # 모델 로딩 중 미리보기 프레임
            return
        self._handle_state(state)

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._label.setText(f"시작/처리 실패: {msg}")
        self._home_btn.show()

    def _record(self, score: float, detail: list[tuple[str, float]] | None = None
                ) -> None:
        add_record(self._name, score, detail or [],
                   datetime.datetime.now().isoformat(), game=self.game_id)

    # ---- 레이아웃 ----
    def resizeEvent(self, e) -> None:
        self._label.setGeometry(0, 0, self.width(), self.height())
        self._view_size = (self.width(), self.height())  # 워커가 읽는 리사이즈 목표
        self._quit_btn.setFixedSize(56, 44)
        self._quit_btn.move(self.width() - 72, 16)
        self._home_btn.adjustSize()
        self._home_btn.move((self.width() - self._home_btn.width()) // 2,
                            int(self.height() * 0.9))
        super().resizeEvent(e)

    def render_once(self) -> None:
        """헤드리스 검증용: 워커 없이 한 프레임 동기 처리(추론+합성)."""
        if self._infer_fn is None or self._source is None:
            return
        frame = self._source.read()
        if frame is None:
            return
        result = self._infer_fn(frame.copy())
        composed, state = self._render_fn(frame, result)
        self._on_ready(composed, state)


class MiniGameView(BaseGameView):
    """1인 미니게임 공통 뷰 — 추정기+주 대상 추적 + 게임 상태머신 + 합성.

    서브클래스는 다음만 정의한다:
      game_id / title(loading_text 겸용) / _make_game(cfg) / _compose(정적)
      GO_STATES / SUCCESS_STATES: 진입 시 효과음을 낼 상태 값 집합
      _detail(state): 리더보드 기록 상세 [(라벨, 값)] 목록
    """

    GO_STATES: frozenset = frozenset()       # 진입 시 go() 효과음
    SUCCESS_STATES: frozenset = frozenset()  # 진입 시 success() 효과음

    def __init__(self):
        super().__init__()
        self._game = None  # 검증 도구 호환용 참조(워커가 생성)
        from PySide6.QtWidgets import QLabel
        self._record_lbl = QLabel("🏆 신기록! New Record!", self)
        self._record_lbl.setStyleSheet(
            "color:#ffd75a; font-size:34px; font-weight:900;"
            "background:rgba(20,16,4,0.65); border:2px solid #ffd75a;"
            "border-radius:14px; padding:10px 26px;")
        self._record_lbl.hide()

    def _make_game(self, cfg: dict):
        raise NotImplementedError

    @staticmethod
    def _compose(disp, primary, state, anim_t=None, popups=None):
        raise NotImplementedError

    def _detail(self, state) -> list[tuple[str, float]]:
        return []

    def _fx_events(self, prev, state, primary, w: int, h: int,
                   now: float) -> list[dict]:
        """상태 변화에서 팝업 이벤트를 뽑는다 (워커 스레드 — Qt 금지).
        반환: [{"text","x","y","at","color"}] — 기본 없음."""
        return []

    def _on_stop(self) -> None:
        self._game = None  # 공유 모델은 core.warm 이 관리 — close 하지 않음
        self._record_lbl.hide()

    def build(self, cfg: dict):
        import collections

        from core.engine import load_settings
        from core.tracker import PrimarySubjectTracker
        from core.warm import get_estimator
        from ui.hud import TrailTracker
        from ui.qtutil import draw_fps, fit_frame

        holder: dict = {}
        start = self._start
        show_fps = bool(cfg.get("showFps", False))
        disp_ts: collections.deque = collections.deque(maxlen=40)
        infer_ts: collections.deque = collections.deque(maxlen=20)
        compose_fn = type(self)._compose

        def infer(frame):
            """추론 스레드 전용(무거움): 공유 모델 + 주 대상 추적."""
            ctx = holder.get("ctx")
            if ctx is None:
                s = load_settings()
                pe = s.get("pose_estimator", {})
                tr = s.get("tracker", {})
                est = get_estimator(
                    num_poses=1,
                    min_detection_confidence=pe.get("min_detection_confidence", 0.5),
                    min_tracking_confidence=pe.get("min_tracking_confidence", 0.5),
                    model_variant=pe.get("model", "auto"),
                )
                tracker = PrimarySubjectTracker(
                    center_weight=tr.get("center_weight", 0.3),
                    min_iou_keep=tr.get("min_iou_keep", 0.2),
                    grace_frames=tr.get("grace_frames", 15),
                    smoothing=tr.get("smoothing", True),
                )
                ctx = (est, tracker, self._make_game(cfg))
                holder["ctx"] = ctx
                self._game = ctx[2]
            est, tracker, _ = ctx
            poses = est.estimate(frame)
            if show_fps:
                infer_ts.append(time.monotonic())
            return tracker.update(poses)

        def render(frame, primary):
            """표시 루프(카메라 fps): 화면 해상도로 먼저 확대 후 HUD.
            게임 갱신도 확대된 좌표로 — 기준선/목표선 픽셀 좌표가 화면과 일치.
            모션 트레일·이벤트 팝업 상태는 이 클로저가 소유(뷰 재시작 시 초기화)."""
            ctx = holder.get("ctx")
            if ctx is None:
                return fit_frame(frame, self._view_size), None  # 모델 로딩 중
            game = ctx[2]
            now = time.monotonic() - start
            disp = fit_frame(frame, self._view_size)
            if disp.shape[:2] != frame.shape[:2] and primary is not None:
                primary = primary.scaled(disp.shape[1] / frame.shape[1],
                                         disp.shape[0] / frame.shape[0])
            state = game.update(primary, now)
            # 손목·머리 잔상 궤적 (compose 의 배경 처리보다 먼저 그려 은은하게)
            trail = holder.setdefault("trail", TrailTracker())
            trail.update(primary)
            trail.draw(disp)
            # 이벤트 팝업 (+1, +Ncm …) — 직전 상태와 비교해 감지
            popups: list = holder.setdefault("popups", [])
            prev = holder.get("prev_state")
            if prev is not None:
                popups.extend(self._fx_events(prev, state, primary,
                                              disp.shape[1], disp.shape[0], now))
                del popups[:-6]  # 폭주 방지
            holder["prev_state"] = state
            popups[:] = [p for p in popups if now - p["at"] < 1.1]
            composed = compose_fn(disp, primary, state, anim_t=now,
                                  popups=list(popups))
            if show_fps:
                disp_ts.append(time.monotonic())
                draw_fps(composed, disp_ts, infer_ts)
            return composed, state

        return infer, render

    # ---- 사운드/기록 (상태 전이 1회성) ----
    def _handle_state(self, state) -> None:
        st = state.state.value
        entered = st != self._prev_state
        if entered and self._sound is not None:
            if st in self.GO_STATES:
                self._sound.go()
            elif st in self.SUCCESS_STATES:
                self._sound.success()
        if st == "done" and not self._saved:
            self._saved = True
            score = getattr(state, "score", None) or 0.0
            from core.leaderboard import top_n
            prev = top_n(1, game=self.game_id)
            is_record = score > 0 and (not prev or score > prev[0].get("total", 0))
            self._record(score, self._detail(state))
            if is_record:
                self._record_lbl.show()  # 신기록 배너 — 구경꾼에게도 보이는 성취
            if self._sound is not None:
                self._sound.fanfare()
                self._sound.speak(state.message)
            self._home_btn.show()
        self._prev_state = st

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._record_lbl.adjustSize()
        self._record_lbl.move((self.width() - self._record_lbl.width()) // 2,
                              int(self.height() * 0.13))
