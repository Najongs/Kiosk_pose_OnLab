"""2인 대결 화면: numPoses=2 추정 → 좌우 배정 → VersusSession → 분할 HUD.

워커/표시 수명주기는 BaseGameView 가 담당 — 이 파일은 대결 고유 로직만:
2인 추정 컨텍스트(build), 사운드 큐, 완료 처리.
"""

from __future__ import annotations

import collections
import time

from core.pose_def import load_pose
from core.scorer import PoseScorer
from core.versus import VersusSession, VState, assign_players
from core.warm import get_estimator
from ui.game_view import BaseGameView
from ui.qtutil import draw_fps, fit_frame
from ui.renderer import compose_versus


class VersusView(BaseGameView):
    game_id = "versus"
    loading_text = "카메라·모델 준비 중… (2인)"

    def __init__(self):
        super().__init__()
        self._vs: VersusSession | None = None  # 검증 도구 호환용 참조
        self._pass = 85.0

    # begin(app_config, source) — BaseGameView.begin 과 시그니처 호환(이름 생략)

    def build(self, cfg: dict):
        self._pass = float(cfg.get("passAccuracy", 85.0))
        pass_acc = self._pass
        start = self._start
        show_fps = bool(cfg.get("showFps", False))
        disp_ts: collections.deque = collections.deque(maxlen=40)
        infer_ts: collections.deque = collections.deque(maxlen=20)
        holder: dict = {}

        def infer(frame):
            """추론 스레드 전용(무거움): 자세 로드·2인 모델·포즈 추정."""
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
            est, _ = ctx
            poses = est.estimate(frame)
            if show_fps:
                infer_ts.append(time.monotonic())
            return poses

        def render(frame, poses):
            """표시 루프(카메라 fps): 화면 해상도로 먼저 확대 후 HUD 를 그린다
            (작은 프레임에 그려서 확대하면 글자·선이 뭉개짐)."""
            ctx = holder.get("ctx")
            if ctx is None:
                return fit_frame(frame, self._view_size), None  # 모델 로딩 중
            _, vs = ctx
            poses = poses or []
            w = frame.shape[1]
            state = vs.update(poses, time.monotonic() - start, w)
            disp = fit_frame(frame, self._view_size)
            if disp.shape[:2] != frame.shape[:2]:
                sx = disp.shape[1] / frame.shape[1]
                sy = disp.shape[0] / frame.shape[0]
                poses = [p.scaled(sx, sy) for p in poses]
            a, b = assign_players(poses, disp.shape[1])  # 좌반=P1, 우반=P2
            composed = compose_versus(disp, a, b, state, pass_acc)
            if show_fps:
                disp_ts.append(time.monotonic())
                draw_fps(composed, disp_ts, infer_ts)
            return composed, state

        return infer, render

    def _on_stop(self) -> None:
        self._vs = None  # 공유 모델은 core.warm 이 관리 — close 하지 않음

    def _handle_state(self, state) -> None:
        if self._sound is not None and state.state.value != self._prev_state:
            if state.state == VState.PLAYING:
                self._sound.go()
            elif state.state == VState.DONE:
                self._sound.fanfare()
                self._sound.speak(state.message)
        self._prev_state = state.state.value
        if state.state == VState.DONE:
            self._home_btn.show()
