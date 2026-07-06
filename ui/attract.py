"""어트랙트 모드(호객 대기 화면) — 라이브 미러.

홈 화면에서 일정 시간 입력이 없으면 전체를 덮고 **카메라에 비치는 행인의
스켈레톤을 실시간으로 보여준다**. 지나가기만 해도 화면이 반응하므로 참여
퍼널의 최대 병목인 "첫 움직임"(docs/콘텐츠/게임_레퍼런스_조사.md B1)을
자동으로 넘겨준다. 무작위 간격의 플러시 연출(C1: 랜덤 주기 > 근접 반응형)과
유인 문구를 함께 재생하고, 아무 곳이나 터치하면 닫히고 홈으로 돌아간다.

카메라를 못 열면 기존 동작 예시 슬라이드쇼로 폴백한다.
"""

from __future__ import annotations

import glob
import json
import os
import random
import re
import time

import numpy as np

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.appconfig import load_app_config
from core.drawing import TextItem, draw_skeleton, draw_texts, panel
from core.games.common import wrist_above_shoulder
from core.sound import Sound
from ui.frame_worker import FrameWorker
from core.i18n import en
from ui.hud import SUB_COLOR, corner_brackets, expanding_rings, msg_pill, vignette
from ui.qtutil import bgr_to_qpixmap, fit_frame

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_EXAMPLES_DIR = os.path.join(_CONFIG_DIR, "examples")
_POSES_DIR = os.path.join(_CONFIG_DIR, "poses")
_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# 원거리에서도 읽히는 짧은 유인 문구 (anim_t 로 순환)
_INVITES = ["지나가다 멈춰 보세요!", "몸을 움직이면 화면이 반응해요",
            "AI 가 당신의 동작을 봅니다", "게임에 도전해 보세요!"]
INVITE_SECONDS = 4.0
_P_COLORS = [(166, 230, 46), (255, 168, 74), (196, 110, 255)]  # BGR


def compose_attract(frame: np.ndarray, poses: list, anim_t: float,
                    flourish_age: float | None,
                    flourish_pos: tuple[float, float]) -> np.ndarray:
    """라이브 미러 화면 합성 (Qt 비의존 — 헤드리스 검증 가능)."""
    h, w = frame.shape[:2]
    texts: list[TextItem] = []
    vignette(frame)
    corner_brackets(frame, anim_t=anim_t)

    hands_up = False
    for i, p in enumerate(poses or []):
        draw_skeleton(frame, p, color=_P_COLORS[i % len(_P_COLORS)])
        hands_up = hands_up or wrist_above_shoulder(p)

    # 무작위 간격 플러시 — 사람이 오기 전에도 화면이 스스로 움직인다
    if flourish_age is not None and flourish_age < 1.2:
        expanding_rings(frame, int(w * flourish_pos[0]),
                        int(h * flourish_pos[1]), flourish_age,
                        color=(160, 231, 127))

    # 상단 브랜딩
    texts.append(TextItem("OnLab · AI 체험 게임", (w // 2, int(h * 0.07)),
                          max(22, h // 26), (140, 235, 190), anchor="mm"))

    # 중앙 유인 문구 — 사람이 보이면 즉시 반응형 문구로 전환
    big = max(40, h // 12)
    if hands_up:
        msg, mc = "좋아요! 바로 그거예요", (255, 230, 90)
        expanding_rings(frame, w // 2, int(h * 0.24), anim_t % 0.8,
                        color=(60, 200, 255))
    elif poses:
        msg, mc = "손을 번쩍 들어 보세요!", (120, 255, 140)
    else:
        msg = _INVITES[int(anim_t / INVITE_SECONDS) % len(_INVITES)]
        mc = (235, 245, 255)
    texts.append(TextItem(msg, (w // 2, int(h * 0.24)), big, mc,
                          anchor="mm", stroke=5))
    sub = en(msg)
    if sub:  # 영어 병기 — 외국인 행인도 유인 문구를 읽을 수 있게
        texts.append(TextItem(sub, (w // 2, int(h * 0.24) + int(big * 0.85)),
                              max(16, big // 3), SUB_COLOR, anchor="mm",
                              stroke=2))

    # 하단 시작 안내 필
    msg_pill(frame, texts, "화면을 터치하면 게임을 고를 수 있어요  ▶",
             int(h * 0.88), max(26, h // 22), (220, 235, 255))
    return draw_texts(frame, texts)


def _display_names() -> dict[str, str]:
    """slug → 한글 표시명 (config/poses/*.json)."""
    names: dict[str, str] = {}
    for p in glob.glob(os.path.join(_POSES_DIR, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            names[os.path.splitext(os.path.basename(p))[0]] = d.get(
                "display_name", "")
        except (OSError, json.JSONDecodeError):
            pass
    return names


class AttractOverlay(QWidget):
    dismissed = Signal()

    def __init__(self, parent=None, interval_ms: int = 2600,
                 source_factory=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background:#05070d;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._source_factory = source_factory

        # ---- 라이브 미러 (기본) ----
        self._live = QLabel(self)
        self._live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._live.hide()
        self._source = None            # 헤드리스 render_once 용
        self._infer_fn = None
        self._render_fn = None
        self._thread: QThread | None = None
        self._worker: FrameWorker | None = None
        self._view_size: tuple[int, int] = (0, 0)
        self._sound: Sound | None = None
        # 플러시 스케줄은 메인 스레드 타이머가 잡고(효과음 재생 겸) 워커가 읽는다
        self._fx = {"at": None, "pos": (0.5, 0.42)}
        self._rng = random.Random()
        self._fx_timer = QTimer(self)
        self._fx_timer.setSingleShot(True)
        self._fx_timer.timeout.connect(self._flourish)

        # ---- 슬라이드쇼 (카메라 폴백) ----
        self._slides = QWidget(self)
        root = QVBoxLayout(self._slides)
        root.setContentsMargins(40, 50, 40, 40)
        title = QLabel("AI 체험 게임에 도전해 보세요!<br>"
                       '<span style="font-size:22px; font-weight:600;'
                       ' color:#8a94ad;">Come try the AI motion games!</span>')
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:52px; font-weight:900; color:#2ee6a6;"
                            "background:transparent;")
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet("background:transparent;")
        self._caption = QLabel("")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet("font-size:24px; color:#9aa4bd;"
                                    "background:transparent;")
        hint = QLabel("▶ 화면을 터치하면 시작됩니다 · Touch to start")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size:28px; font-weight:700; color:#eef2fb;"
                           "background:rgba(46,230,166,0.14); border-radius:16px;"
                           "padding:14px;")
        root.addWidget(title)
        root.addWidget(self._img, 1)
        root.addWidget(self._caption)
        root.addSpacing(14)
        root.addWidget(hint)
        self._slides.hide()

        self._paths = sorted(
            p for ext in _EXTS
            for p in glob.glob(os.path.join(_EXAMPLES_DIR, f"*{ext}")))
        self._names = _display_names()
        self._idx = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._next)

    def has_content(self) -> bool:
        return self._source_factory is not None or bool(self._paths)

    # ---- 수명주기 ----
    def showEvent(self, e) -> None:
        # 이미 수동으로 시작된 경우(헤드리스 검증) 재시작하지 않는다
        if self._worker is None and self._source is None:
            if self._source_factory is not None:
                self._begin_live(self._source_factory)
            else:
                self._show_slides()
        super().showEvent(e)

    def hideEvent(self, e) -> None:
        self._stop_live()
        self._timer.stop()
        super().hideEvent(e)

    def mousePressEvent(self, e) -> None:
        self.hide()  # hideEvent 가 워커를 세워 카메라를 즉시 반납
        self.dismissed.emit()

    def resizeEvent(self, e) -> None:
        self._live.setGeometry(self.rect())
        self._slides.setGeometry(self.rect())
        self._view_size = (self.width(), self.height())
        super().resizeEvent(e)

    # ---- 라이브 미러 ----
    def _begin_live(self, source) -> None:
        """source: 팩토리(callable) 또는 FrameSource 인스턴스(헤드리스)."""
        self._stop_live()
        cfg = load_app_config()
        if self._sound is None:
            self._sound = Sound(bool(cfg.get("sound", True)), False)
        self._slides.hide()
        self._live.show()
        self._live.setText("")
        start = time.monotonic()
        fx = self._fx
        holder: dict = {}

        def infer(frame):
            est = holder.get("est")
            if est is None:
                from core.warm import get_estimator
                est = get_estimator(num_poses=2)  # 대결과 같은 캐시 — 추가 로드 없음
                holder["est"] = est
            return est.estimate(frame)

        def render(frame, poses):
            now = time.monotonic() - start
            disp = fit_frame(frame, self._view_size)
            if disp.shape[:2] != frame.shape[:2] and poses:
                sx = disp.shape[1] / frame.shape[1]
                sy = disp.shape[0] / frame.shape[0]
                poses = [p.scaled(sx, sy) for p in poses]
            at = fx.get("at")
            age = (time.monotonic() - at) if at is not None else None
            composed = compose_attract(disp, poses or [], now, age, fx["pos"])
            return composed, None

        self._infer_fn = infer
        self._render_fn = render
        if not callable(source):
            self._source = source
        self._thread = QThread(self)
        self._worker = FrameWorker(source, infer, render)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_frame)
        self._worker.failed.connect(self._on_live_failed)
        self._worker.stopped.connect(self._thread.quit)
        self._thread.start()
        self._schedule_flourish(first=True)

    def _stop_live(self) -> None:
        self._fx_timer.stop()
        if self._worker is not None:
            self._worker.stop()
            for sig, slot in ((self._worker.ready, self._on_frame),
                              (self._worker.failed, self._on_live_failed)):
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

    def _on_frame(self, composed, _state) -> None:
        pix = bgr_to_qpixmap(composed)
        if pix.width() > self._live.width() or pix.height() > self._live.height():
            pix = pix.scaled(self._live.size(),
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        self._live.setPixmap(pix)

    def _on_live_failed(self, msg: str) -> None:
        print(f"[어트랙트] 라이브 미러 실패 → 슬라이드쇼 폴백: {msg}")
        self._stop_live()
        self._live.hide()
        self._show_slides()

    def _schedule_flourish(self, first: bool = False) -> None:
        # 2.5~6초 무작위 간격 — 근접 반응형이 아니라 '미리 움직이는' 화면
        self._fx_timer.start(int(self._rng.uniform(700 if first else 2500, 6000)))

    def _flourish(self) -> None:
        self._fx["pos"] = (self._rng.uniform(0.2, 0.8),
                           self._rng.uniform(0.3, 0.6))
        self._fx["at"] = time.monotonic()
        if self._sound is not None:
            self._sound.tick()  # 은은한 호객음 (설정 sound 꺼짐이면 무음)
        self._schedule_flourish()

    def render_once(self) -> None:
        """헤드리스 검증용: 워커 없이 한 프레임 동기 처리."""
        if self._infer_fn is None or self._source is None:
            return
        frame = self._source.read()
        if frame is None:
            return
        poses = self._infer_fn(frame.copy())
        composed, _ = self._render_fn(frame, poses)
        self._on_frame(composed, None)

    # ---- 슬라이드쇼 폴백 ----
    def _show_slides(self) -> None:
        if not self._paths:
            return
        self._slides.show()
        self._next()
        self._timer.start()

    def _next(self) -> None:
        if not self._paths:
            return
        path = self._paths[self._idx % len(self._paths)]
        self._idx += 1
        pix = QPixmap(path)
        if pix.isNull():
            return
        avail = self._img.size()
        if avail.width() > 32 and avail.height() > 32:
            pix = pix.scaled(avail, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        self._img.setPixmap(pix)
        slug = os.path.splitext(os.path.basename(path))[0]
        base = re.sub(r"_\d+$", "", slug)  # 연속동작 스텝(_1, _2) 접미 제거
        self._caption.setText(self._names.get(base) or base.replace("_", " "))
