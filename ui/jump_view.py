"""높이뛰기 측정 화면."""

from __future__ import annotations

from core.games.jump import JumpGame
from ui.game_renderers import compose_jump
from ui.game_view import MiniGameView


class JumpView(MiniGameView):
    game_id = "jump"
    loading_text = "높이뛰기 준비 중…"

    GO_STATES = frozenset({"ready"})
    SUCCESS_STATES = frozenset({"rest"})

    def _make_game(self, cfg: dict) -> JumpGame:
        return JumpGame(
            attempts=int(cfg.get("jumpAttempts", 3)),
            calib_seconds=float(cfg.get("jumpCalibSeconds", 2.0)),
            target_cm=float(cfg.get("jumpTargetCm", 30.0)),
        )

    @staticmethod
    def _compose(disp, primary, state, anim_t=None):
        return compose_jump(disp, primary, state, anim_t=anim_t)

    def _detail(self, state) -> list[tuple[str, float]]:
        return [(f"{i + 1}회 (cm)", cm) for i, cm in enumerate(state.attempts_cm)]
