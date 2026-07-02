"""미니게임 뷰 헤드리스 검증: offscreen 렌더 + 상태 진행 확인 + 스크린샷.

실행:
    QT_QPA_PLATFORM=offscreen python tools/verify_games.py

정지 이미지 특성상 도달 가능한 상태까지만 확인한다:
  반응속도: 손 안 든 채 타임아웃 라운드 소진 → DONE (+리더보드 기록)
  높이뛰기: 캘리브레이션 통과 → READY (점프는 test_games.py 합성 데이터로 검증)
  팔굽혀펴기: COUNTING 진입 → 제한시간 종료 → DONE
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "ui_py")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from core import leaderboard  # noqa: E402
from core.appconfig import load_app_config  # noqa: E402
from core.frame_source import ImageSource  # noqa: E402
from ui.jump_view import JumpView  # noqa: E402
from ui.pushup_view import PushupView  # noqa: E402
from ui.qtutil import DARK_QSS  # noqa: E402
from ui.reaction_view import ReactionView  # noqa: E402

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"  FAIL: {msg}")


def run_view(app, view, cfg: dict, image: str, name: str, seconds: float,
             until=None) -> object:
    """뷰를 헤드리스로 돌리고 마지막 게임 상태를 반환. until(state)->bool 이
    참이 되거나 seconds 경과 시 종료."""
    src = ImageSource(os.path.join(ROOT, "testdata", image), loop=True)
    view.resize(1280, 800)
    view.show()
    view.begin(cfg, src, name)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        view.render_once()
        app.processEvents()
        g = view._game
        if g is not None and until is not None:
            st = getattr(g, "state", None)
            if st is not None and until(st):
                break
    # 워커 스레드가 목표 상태로 전이시킨 직후 break 된 경우, 스냅샷 처리
    # (기록/홈버튼)가 메인 스레드에 아직 안 왔을 수 있다 — 몇 프레임 플러시.
    for _ in range(3):
        view.render_once()
        app.processEvents()
    view.grab().save(os.path.join(OUT, f"7_game_{view.game_id}.png"))
    print(f"saved 7_game_{view.game_id}.png  (state={getattr(view._game, 'state', None)})")
    return view._game


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    leaderboard.clear()
    cfg = load_app_config()

    # ---- 반응속도: 손을 안 드는 이미지 → 타임아웃으로 라운드 소진 → DONE ----
    from core.games.reaction import RState
    cfg_r = dict(cfg)
    cfg_r.update(reactionRounds=2, reactionMinDelay=0.2, reactionMaxDelay=0.4)
    rv = ReactionView()
    game = run_view(app, rv, cfg_r, "mountain.jpg", "테스터R", 25.0,
                    until=lambda s: s == RState.DONE)
    check(game is not None and game.state == RState.DONE,
          f"반응속도 DONE 도달 실패: {getattr(game, 'state', None)}")
    check(game is not None and len(game.times_ms) == 2,
          f"반응속도 기록 2개여야 함: {getattr(game, 'times_ms', None)}")
    rv.stop()

    # ---- 높이뛰기: 정지 이미지 → 캘리브레이션 통과 → READY ----
    from core.games.jump import JState
    cfg_j = dict(cfg)
    cfg_j.update(jumpCalibSeconds=1.0)
    jv = JumpView()
    game = run_view(app, jv, cfg_j, "mountain.jpg", "테스터J", 12.0,
                    until=lambda s: s == JState.READY)
    check(game is not None and game.state == JState.READY,
          f"높이뛰기 READY 도달 실패: {getattr(game, 'state', None)}")
    check(game is not None and game.baseline is not None, "기준선 미설정")
    jv.stop()

    # ---- 팔굽혀펴기: COUNTING 진입 → 제한시간 종료 → DONE ----
    from core.games.pushup import PState
    cfg_p = dict(cfg)
    cfg_p.update(pushupMode="timed", pushupSeconds=3.0)
    pv = PushupView()
    game = run_view(app, pv, cfg_p, "mountain.jpg", "테스터P", 15.0,
                    until=lambda s: s == PState.DONE)
    check(game is not None and game.state == PState.DONE,
          f"팔굽혀펴기 DONE 도달 실패: {getattr(game, 'state', None)}")
    pv.stop()

    # ---- 리더보드: 게임별 기록 분리 확인 ----
    rec_r = leaderboard.top_n(5, game="reaction")
    rec_p = leaderboard.top_n(5, game="pushup")
    check(len(rec_r) == 1 and rec_r[0]["name"] == "테스터R",
          f"reaction 리더보드 기록 오류: {rec_r}")
    check(len(rec_p) == 1 and rec_p[0]["name"] == "테스터P",
          f"pushup 리더보드 기록 오류: {rec_p}")
    check(leaderboard.top_n(5, game="stretch") == [],
          "stretch 리더보드는 비어 있어야 함")
    leaderboard.clear()

    print("RESULT:", "FAIL" if FAILURES else "OK")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
