"""반응속도 테스트 화면."""

from __future__ import annotations

import random

from core.games.reaction import ReactionGame
from ui.game_renderers import compose_reaction
from ui.game_view import MiniGameView


class ReactionView(MiniGameView):
    game_id = "reaction"
    loading_text = "반응속도 테스트 준비 중… · Loading Reaction Test"

    GO_STATES = frozenset({"signal"})
    # REST 는 부정 출발/시간 초과로도 진입하므로 SUCCESS_STATES 로 다루지 않고
    # 정상 반응(기록 있음 + 실패 아님)일 때만 _handle_state 에서 직접 성공음.

    def _handle_state(self, state) -> None:
        if (self._sound is not None and state.state.value == "rest"
                and self._prev_state != "rest"
                and not state.false_start and not state.timed_out
                and state.last_ms is not None):
            self._sound.success()
        super()._handle_state(state)

    def _make_game(self, cfg: dict) -> ReactionGame:
        return ReactionGame(
            rounds=int(cfg.get("reactionRounds", 5)),
            min_delay=float(cfg.get("reactionMinDelay", 1.5)),
            max_delay=float(cfg.get("reactionMaxDelay", 4.0)),
            rng=random.Random(),
        )

    @staticmethod
    def _compose(disp, primary, state, anim_t=None, popups=None):
        return compose_reaction(disp, primary, state, anim_t=anim_t,
                                popups=popups)

    def _detail(self, state) -> list[tuple[str, float]]:
        return [(f"{i + 1}회 (ms)", ms) for i, ms in enumerate(state.times_ms)]
