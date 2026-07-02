"""헤드리스 2인 대결 검증: 2인 이미지로 VersusView 를 offscreen 렌더 + 상태 확인.
실행: QT_QPA_PLATFORM=offscreen python tools/verify_versus.py"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "ui_py")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.frame_source import ImageSource  # noqa: E402
from core.versus import VState  # noqa: E402
from ui.versus_view import VersusView  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    cfg = {"poseSet": ["tpose", "overhead_reach"], "passAccuracy": 0,
           "countdownSeconds": 1, "resultSeconds": 1, "holdSecondsOverride": 1,
           "sound": False, "voice": False}
    view = VersusView()
    view.resize(1280, 720)
    view.show()
    app.processEvents()
    src = ImageSource(os.path.join(os.path.dirname(OUT), "..", "testdata", "two_people.jpg"),
                      loop=True)
    view.begin(cfg, src)

    saw_playing = False
    saw_done = False
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        view.render_once()
        app.processEvents()
        vs = view._vs
        if vs is not None and vs.state == VState.PLAYING and not saw_playing:
            # 두 명 검출 + playing 화면 저장
            p1p = vs.holds[0] is not None
            view.grab().save(os.path.join(OUT, "5_versus_playing.png"))
            print("saw playing; players holds ready:", p1p)
            saw_playing = True
        if vs is not None and vs.state == VState.DONE and not saw_done:
            view.grab().save(os.path.join(OUT, "6_versus_done.png"))
            print("done totals:", vs.totals, "winner-msg via state")
            saw_done = True
            break
        time.sleep(0.06)

    print("RESULT:", "OK" if (saw_playing and saw_done) else f"playing={saw_playing} done={saw_done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
