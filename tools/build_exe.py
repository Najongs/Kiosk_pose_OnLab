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
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if sys.platform == "win32" else ":"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--console", action="store_true",
                    help="콘솔 창 표시 (진단 로그 확인용)")
    args = ap.parse_args()

    if shutil.which("pyinstaller") is None:
        print("PyInstaller 가 없습니다:  pip install pyinstaller")
        return 1

    cmd = [
        "pyinstaller", "--noconfirm", "--name", "OnLab",
        "--icon", os.path.join(ROOT, "assets", "icon.ico"),
        # 앱이 읽고/쓰는 데이터 — _internal/ 아래로 들어가 코드의
        # ROOT(=모듈 기준 상위 폴더) 경로 계산과 일치한다
        "--add-data", f"config{SEP}config",
        "--add-data", f"models{SEP}models",
        "--add-data", f"assets{SEP}assets",
        # mediapipe: 네이티브 모듈 + 데이터 통째 수집
        "--collect-all", "mediapipe",
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
