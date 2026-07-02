"""자세별 예시 이미지/참조 스켈레톤 상태 점검.

세션 화면 왼쪽 가이드 박스는 다음 우선순위로 표시된다:
  1. config/examples/<자세명>.png|jpg|jpeg|webp  (예시 이미지)
  2. 관리자 화면에서 캡처한 참조 스켈레톤 (config/refs.json)
  3. 둘 다 없으면 "예시 준비 중"

이 스크립트는 어떤 자세가 왜 "예시 준비 중"으로 뜨는지 한눈에 보여준다.
    python tools/check_examples.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.appconfig import load_app_config  # noqa: E402
from core.pose_def import list_poses, load_pose  # noqa: E402
from core.refs import has_ref  # noqa: E402

EXAMPLES = os.path.join(ROOT, "config", "examples")
EXTS = (".png", ".jpg", ".jpeg", ".webp")


def example_path(name: str) -> str | None:
    for ext in EXTS:
        p = os.path.join(EXAMPLES, name + ext)
        if os.path.isfile(p):
            return p
    return None


def main() -> int:
    cfg = load_app_config()
    active = set(cfg.get("poseSet", []))
    try:
        import json
        courses = json.load(open(os.path.join(ROOT, "config", "courses.json"),
                                 encoding="utf-8"))
        for c in courses:
            active.update(c.get("poses", []))
    except Exception:
        pass

    missing = []
    print(f"{'자세':24s} {'표시명':20s} {'예시이미지':10s} {'참조':6s} 가이드")
    print("-" * 78)
    for name in list_poses():
        d = load_pose(name)
        ex = example_path(name)
        ref = has_ref(name)
        guide = "이미지" if ex else ("스켈레톤" if ref else "예시 준비 중 ←")
        mark = "*" if name in active else " "
        print(f"{mark}{name:23s} {d.display_name:20s} "
              f"{'있음' if ex else '없음':10s} {'있음' if ref else '없음':6s} {guide}")
        if not ex and not ref:
            missing.append(name)
    print("-" * 78)
    print("* = 현재 자세 세트/코스에 포함된 자세")
    if missing:
        print(f"\n'예시 준비 중'으로 뜨는 자세 {len(missing)}개: {', '.join(missing)}")
        print("해결: config/examples/<자세명>.png 추가  또는  관리자 → 카메라로 캡처")
    else:
        print("\n모든 자세에 가이드가 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
