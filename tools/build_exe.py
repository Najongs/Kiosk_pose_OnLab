"""배포용 실행파일 빌드 (PyInstaller).

Windows 에서 실행하면 dist/OnLab/OnLab.exe 가 만들어진다 (폴더 통째 배포).

    pip install pyinstaller
    python tools/build_exe.py            # 창 모드 (콘솔 숨김, 배포용)
    python tools/build_exe.py --console  # 콘솔 표시 (문제 진단용)

선택 이유/주의:
- onedir(폴더) 모드: config/(설정·리더보드·참조), 카메라 캐시 등을 실행 중에
  기록해야 하므로 임시폴더에 풀리는 onefile 보다 폴더 배포가 맞다.
  배포 시 dist/OnLab 폴더를 압축해서 전달하면 된다.
- mediapipe 는 바이너리 모듈이 많아 --collect-all 로 통째 수집한다.
- 용량: PySide6+mediapipe+opencv 때문에 700MB±. 정상이다.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if sys.platform == "win32" else ":"

# 빌드 전 사전 점검: 이 인터프리터에서 임포트가 되어야 exe 에도 들어간다.
# (pyinstaller 를 다른 파이썬에 설치해 두고 빌드하면 "빌드는 성공,
#  실행하면 ModuleNotFoundError" 가 되는 것이 최다 빈도 사고)
_REQUIRED = ["mediapipe", "cv2", "numpy", "PIL", "PySide6", "PyInstaller"]
_PROJECT = ["core.engine", "core.games.reaction", "core.games.jump",
            "core.games.pushup", "core.smoothing", "ui.main_window",
            "ui.game_registry", "ui.attract"]


def _preflight() -> bool:
    sys.path.insert(0, ROOT)
    ok = True
    for name in _REQUIRED + _PROJECT:
        try:
            importlib.import_module(name)
        except Exception as e:
            print(f"[사전 점검 실패] import {name} → {type(e).__name__}: {e}")
            ok = False
    if not ok:
        print(f"\n이 파이썬({sys.executable})에 위 모듈이 없습니다.")
        print("앱 의존성이 설치된 같은 환경에 pyinstaller 를 설치한 뒤")
        print("그 환경의 python 으로 이 스크립트를 실행하세요:")
        print("  python -m pip install -r requirements.txt pyinstaller")
        print("  python tools/build_exe.py")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--console", action="store_true",
                    help="콘솔 창 표시 (진단 로그 확인용)")
    args = ap.parse_args()

    if not _preflight():
        return 1

    cmd = [
        # 반드시 '이 스크립트를 실행한 파이썬'의 PyInstaller 를 쓴다 —
        # PATH 의 pyinstaller 가 다른 환경을 가리키는 사고 방지
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--name", "OnLab",
        "--icon", os.path.join(ROOT, "assets", "icon.ico"),
        # 앱이 읽고/쓰는 데이터 — _internal/ 아래로 들어가 코드의
        # ROOT(=모듈 기준 상위 폴더) 경로 계산과 일치한다
        "--add-data", f"config{SEP}config",
        "--add-data", f"models{SEP}models",
        "--add-data", f"assets{SEP}assets",
        # mediapipe: 네이티브 모듈 + 데이터 통째 수집
        "--collect-all", "mediapipe",
        # 지연 임포트 모듈 명시 (정적 분석 누락 대비 보험)
        "--hidden-import", "ui.session_view",
        "--hidden-import", "ui.versus_view",
        "--hidden-import", "ui.reaction_view",
        "--hidden-import", "ui.jump_view",
        "--hidden-import", "ui.pushup_view",
        "--hidden-import", "core.warm",
        # 쓰지 않는 대형 Qt 모듈 제외 (용량 절감)
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtCharts",
        "main.py",
    ]
    if not args.console:
        cmd.insert(1, "--windowed")

    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode == 0:
        out = os.path.join(ROOT, "dist", "OnLab")
        print(f"\n빌드 완료: {out}")
        print("배포: 이 폴더를 통째로 복사/압축하세요. 실행 파일: OnLab.exe")
        print("설정·리더보드는 OnLab/_internal/config/ 에 저장됩니다.")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
