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
    def _compose(disp, primary, state, anim_t=None, popups=None):
        return compose_jump(disp, primary, state, anim_t=anim_t, popups=popups)

    def _fx_events(self, prev, state, primary, w, h, now) -> list[dict]:
        # 착지(기록 확정) 순간 — 머리 위에 "+Ncm" 팝업
        if len(state.attempts_cm) > len(prev.attempts_cm) and state.last_cm:
            y = int(state.current_head_y or h * 0.35)
            return [{"text": f"+{state.last_cm:.0f}cm", "x": w // 2,
                     "y": max(80, y - 60), "at": now, "color": (140, 235, 255)}]
        return []

    def _detail(self, state) -> list[tuple[str, float]]:
        return [(f"{i + 1}회 (cm)", cm) for i, cm in enumerate(state.attempts_cm)]
