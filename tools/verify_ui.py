"""헤드리스 UI 검증: 홈/관리자/세션 화면을 offscreen 으로 스크린샷 + 리더보드 기록 확인.

실행:
    QT_QPA_PLATFORM=offscreen python tools/verify_ui.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "ui_py")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from core import leaderboard  # noqa: E402
from core.appconfig import load_app_config, reset_app_config, save_app_config  # noqa: E402
from core.frame_source import ImageSource  # noqa: E402
from ui.admin_dialog import AdminDialog  # noqa: E402
from ui.home import HomeWidget  # noqa: E402
from ui.qtutil import DARK_QSS  # noqa: E402
from ui.session_view import SessionView  # noqa: E402


def shot(widget, name):
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)

    # 리더보드 시드
    leaderboard.clear()
    for n, t in [("지민", 92), ("현우", 88), ("서연", 81)]:
        leaderboard.add_record(n, t, [], "")

    # 홈
    home = HomeWidget()
    home.resize(1280, 800)
    home.show()
    app.processEvents()
    shot(home, "1_home.png")

    # 관리자
    admin = AdminDialog(0)
    admin.resize(560, 760)
    admin.show()
    app.processEvents()
    shot(admin, "2_admin.png")
    admin.close()

    # 세션 (빠른 설정으로 완료까지 → 리더보드 기록 확인)
    saved = load_app_config()
    save_app_config({
        **saved,
        "poseSet": ["forward_bend"], "passAccuracy": 55,
        "countdownSeconds": 1, "resultSeconds": 1, "holdSecondsOverride": 1,
        "sound": False, "voice": False,
    })
    leaderboard.clear()
    sv = SessionView()
    sv.resize(1280, 800)
    sv.show()
    app.processEvents()
    src = ImageSource(os.path.join(os.path.dirname(OUT), "..", "testdata", "seated_fold.jpg"), loop=True)
    sv.begin("테스터", load_app_config(), src)

    got_scoring = False
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        sv.render_once()
        app.processEvents()
        if not got_scoring and sv._engine is not None:
            # 채점 중 프레임 하나 저장
            from core.session import State
        time.sleep(0.08)
        if not got_scoring:
            shot(sv, "3_session.png")
            got_scoring = True
        if sv._saved:
            break

    shot(sv, "4_session_last.png")
    recs = leaderboard.top_n(5)
    print("leaderboard after session:", recs)

    # 설정 복구
    reset_app_config()
    leaderboard.clear()
    print("RESULT:", "OK" if sv._saved and recs else "INCOMPLETE (saved=%s)" % sv._saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
