"""어트랙트 라이브 미러 헤드리스 검증: offscreen 렌더 + 스크린샷.

실행:
    QT_QPA_PLATFORM=offscreen python tools/verify_attract.py
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

from core.frame_source import ImageSource  # noqa: E402
from ui.attract import AttractOverlay  # noqa: E402
from ui.qtutil import DARK_QSS  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    ok = True

    # 라이브 미러: 이미지 소스로 스켈레톤 감지 + 합성 확인
    ov = AttractOverlay(source_factory=None)
    ov.resize(1280, 800)
    src = ImageSource(os.path.join(ROOT, "testdata", "two_people.jpg"), loop=True)
    ov._begin_live(src)
    ov.show()
    deadline = time.monotonic() + 20
    got = False
    while time.monotonic() < deadline:
        ov.render_once()
        app.processEvents()
        if ov._live.pixmap() and not ov._live.pixmap().isNull():
            got = True
            break
    # 플러시 연출 프레임도 한 장
    ov._flourish()
    for _ in range(3):
        ov.render_once()
        app.processEvents()
    ov.grab().save(os.path.join(OUT, "8_attract_live.png"))
    print("saved 8_attract_live.png")
    if not got:
        print("  FAIL: 라이브 미러 픽스맵 미생성")
        ok = False
    ov._stop_live()

    # 슬라이드쇼 폴백: 카메라 실패 시 기존 화면으로 전환되는지
    ov2 = AttractOverlay(source_factory=None)
    ov2.resize(1280, 800)
    ov2.show()
    app.processEvents()
    ov2._on_live_failed("verify: 강제 폴백")
    app.processEvents()
    if ov2.has_content() and not ov2._slides.isVisible():
        print("  FAIL: 폴백 슬라이드쇼 미표시")
        ok = False
    ov2.grab().save(os.path.join(OUT, "9_attract_fallback.png"))
    print("saved 9_attract_fallback.png")
    ov2.hide()

    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
