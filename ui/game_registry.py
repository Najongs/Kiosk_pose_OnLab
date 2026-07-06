"""게임 레지스트리 — 홈 카드·네비게이션·리더보드 탭의 단일 출처.

새 게임 추가 절차:
  1) core/games/<게임>.py 상태머신 + ui/game_renderers.py compose_<게임>
  2) ui/<게임>_view.py 에 MiniGameView 서브클래스
  3) 여기 REGISTRY 에 GameDef 한 줄 추가 — 홈 카드/전환/리더보드 탭 자동 생성

start 어댑터가 뷰별 begin 시그니처 차이를 흡수한다 (SessionView/VersusView 는
기존 시그니처를 유지해야 함 — tools/verify_ui.py 등이 positional 로 호출).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class GameDef:
    id: str
    title: str
    subtitle: str
    emoji: str
    accent: str                 # 카드 좌측 스트라이프 색 (hex)
    make_view: Callable         # () -> QWidget (지연 import — 시작 시간 절약)
    start: Callable             # (view, params: dict, cfg: dict, factory) -> None
    board: bool = True          # 리더보드 탭 표시 여부
    extra: dict = field(default_factory=dict)
    title_en: str = ""          # 영어 보조 표기 (홈 카드 — 외국인 방문객용)
    subtitle_en: str = ""


def _cfg_with_poses(cfg: dict, poses: list | None) -> dict:
    if poses:
        cfg = dict(cfg)
        cfg["poseSet"] = list(poses)
    return cfg


def _make_stretch():
    from ui.session_view import SessionView
    return SessionView()


def _start_stretch(view, params: dict, cfg: dict, factory) -> None:
    view.begin(params.get("name", ""), _cfg_with_poses(cfg, params.get("poses")),
               factory)


def _make_versus():
    from ui.versus_view import VersusView
    return VersusView()


def _start_versus(view, params: dict, cfg: dict, factory) -> None:
    view.begin(cfg, factory)


def _make_reaction():
    from ui.reaction_view import ReactionView
    return ReactionView()


def _make_jump():
    from ui.jump_view import JumpView
    return JumpView()


def _make_pushup():
    from ui.pushup_view import PushupView
    return PushupView()


def _start_minigame(view, params: dict, cfg: dict, factory) -> None:
    view.begin(cfg, factory, params.get("name", ""))


# 카드 순서: 크고 눈에 띄는 전신 동작 게임을 앞에 — 플레이 모습 자체가 호객
# (docs/content/game-references.md C3: 과장된 전신 동작이 유인 트리거)
REGISTRY: list[GameDef] = [
    GameDef("reaction", "반응속도 테스트", "신호가 뜨면 최대한 빨리 손 들기",
            "⚡", "#ffdc40", _make_reaction, _start_minigame,
            title_en="Reaction Test",
            subtitle_en="Raise your hand fast when the signal appears"),
    GameDef("jump", "높이뛰기", "제자리 점프 높이 측정 — 목표선을 넘겨라",
            "🦘", "#4aa8ff", _make_jump, _start_minigame,
            title_en="High Jump",
            subtitle_en="Jump on the spot — clear the target line"),
    GameDef("stretch", "스트레칭 코스", "안내 자세를 따라 하고 유연성 점수 받기",
            "🧘", "#2ee6a6", _make_stretch, _start_stretch,
            title_en="Stretching Course",
            subtitle_en="Follow the poses and get a flexibility score"),
    GameDef("versus", "2인 대결", "화면을 반씩 나눠 같은 자세로 대결",
            "⚔️", "#ff6ec4", _make_versus, _start_versus, board=False,
            title_en="2-Player Battle",
            subtitle_en="Split screen — same pose, higher score wins"),
    GameDef("pushup", "팔굽혀펴기", "개수 자동 카운트 + 자세 피드백",
            "💪", "#ff8a4a", _make_pushup, _start_minigame,
            title_en="Push-ups",
            subtitle_en="Auto rep counting with form feedback"),
]

GAMES: dict[str, GameDef] = {g.id: g for g in REGISTRY}

# 리더보드 탭: (game_id, 라벨)
BOARD_TABS: list[tuple[str, str]] = [
    (g.id, g.title) for g in REGISTRY if g.board]
