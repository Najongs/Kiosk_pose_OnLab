"""팔굽혀펴기 검사 화면."""

from __future__ import annotations

from core.games.pushup import PushupGame
from ui.game_renderers import compose_pushup
from ui.game_view import MiniGameView


class PushupView(MiniGameView):
    game_id = "pushup"
    loading_text = "팔굽혀펴기 검사 준비 중…"

    GO_STATES = frozenset({"counting"})

    def __init__(self):
        super().__init__()
        self._prev_reps = 0

    def _make_game(self, cfg: dict) -> PushupGame:
        self._prev_reps = 0
        return PushupGame(
            mode=str(cfg.get("pushupMode", "timed")),
            duration=float(cfg.get("pushupSeconds", 30.0)),
            target_reps=int(cfg.get("pushupTargetReps", 15)),
            up_angle=float(cfg.get("pushupUpAngle", 150.0)),
            down_angle=float(cfg.get("pushupDownAngle", 95.0)),
        )

    @staticmethod
    def _compose(disp, primary, state, anim_t=None, popups=None):
        return compose_pushup(disp, primary, state, anim_t=anim_t,
                              popups=popups)

    def _fx_events(self, prev, state, primary, w, h, now) -> list[dict]:
        # 개수 인정 순간 — 카운터 옆에 "+1" 팝업
        if state.reps > prev.reps:
            color = (255, 230, 140) if state.good_reps > prev.good_reps \
                else (255, 170, 150)  # 자세 나쁜 rep 은 옅은 붉은기
            return [{"text": "+1", "x": int(w * 0.845), "y": int(h * 0.27),
                     "at": now, "color": color}]
        return []

    def _handle_state(self, state) -> None:
        # 개수 증가마다 틱 효과음
        if self._sound is not None and state.reps > self._prev_reps:
            self._sound.tick()
        self._prev_reps = state.reps
        super()._handle_state(state)

    def _detail(self, state) -> list[tuple[str, float]]:
        return [("개수", float(state.reps)),
                ("바른 자세", float(state.good_reps))]
