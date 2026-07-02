"""OnLab 데스크톱 앱 진입점.

사용법:
    python main.py                          # 카메라 0번, 전체화면 (홈→세션)
    python main.py --source testdata/ --windowed --loop   # 카메라 없이 테스트
    python main.py --source video.mp4

헤드리스 UI 검증은 tools/verify_ui.py 참고 (offscreen 스크린샷).
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.appconfig import load_app_config  # noqa: E402
from core.engine import load_settings  # noqa: E402
from core.frame_source import CameraSource, ImageSource, VideoFileSource  # noqa: E402

_IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def make_source_factory(source_arg: str, settings: dict, loop: bool):
    def factory():
        if source_arg.isdigit():
            cam = settings.get("camera", {})
            return CameraSource(int(source_arg), cam.get("width", 1280),
                                cam.get("height", 720), cam.get("fps", 30))
        if os.path.isdir(source_arg) or os.path.splitext(source_arg)[1].lower() in _IMG_EXTS:
            return ImageSource(source_arg, loop=loop)
        return VideoFileSource(source_arg)
    return factory


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="카메라 인덱스 또는 이미지/폴더/영상")
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--loop", action="store_true", help="이미지/폴더 반복(테스트)")
    args = ap.parse_args()

    settings = load_settings()
    load_app_config()  # 존재 확인/기본 생성 트리거는 아니지만 조기 검증

    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    cam_index = int(args.source) if args.source.isdigit() else 0
    # 이미지/폴더 소스는 키오스크처럼 계속 돌도록 기본 반복
    factory = make_source_factory(args.source, settings, loop=True)
    win = MainWindow(factory, camera_index=cam_index, fullscreen=not args.windowed)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
