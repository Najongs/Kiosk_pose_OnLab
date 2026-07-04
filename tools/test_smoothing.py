"""One Euro 스무딩 단위 테스트 — 합성 신호로 떨림 감소·지연·리셋 검증.

실행: python tools/test_smoothing.py  →  RESULT: OK / FAIL
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core.pose_estimator import PersonPose
from core.smoothing import OneEuroFilter, PoseSmoother
from core.tracker import PrimarySubjectTracker

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"  FAIL: {msg}")


def test_jitter_reduction() -> None:
    """정지한 점 + 노이즈 → 필터 출력의 표준편차가 크게 줄어야 한다."""
    rng = random.Random(42)
    f = OneEuroFilter(min_cutoff=1.0, beta=0.015)
    raw, smoothed = [], []
    for i in range(120):
        x = np.array([100.0 + rng.gauss(0, 3.0)])  # 3px 떨림
        raw.append(x[0])
        smoothed.append(f(x, i / 30.0)[0])
    raw_std = float(np.std(raw[30:]))
    sm_std = float(np.std(smoothed[30:]))
    print(f"  정지 떨림: raw std {raw_std:.2f}px → smoothed {sm_std:.2f}px")
    check(sm_std < raw_std * 0.5, f"떨림이 절반 이하로 줄어야 함: {sm_std:.2f}")


def test_fast_motion_lag() -> None:
    """빠르게 움직일 때는 필터가 풀려 지연이 작아야 한다 (적응형)."""
    f = OneEuroFilter(min_cutoff=1.0, beta=0.015)
    lag = 0.0
    for i in range(60):
        true = 100.0 + i * 20.0  # 프레임당 20px 이동 (빠른 동작)
        out = f(np.array([true]), i / 30.0)[0]
        lag = true - out
    print(f"  빠른 이동 지연: {lag:.1f}px (프레임당 20px 이동 중)")
    check(lag < 40.0, f"지연이 2프레임 이동량 미만이어야 함: {lag:.1f}px")


def test_reset_on_new_person() -> None:
    """사람이 바뀌면(리셋) 이전 궤적에 이어붙지 않아야 한다."""
    sm = PoseSmoother()
    kp = np.zeros((33, 3), np.float32)
    kp[:, 2] = 1.0
    kp[:, 0] = 100.0
    p1 = PersonPose(keypoints=kp, bbox=(90, 0, 110, 100))
    for i in range(10):
        sm.apply(p1, i / 30.0)
    sm.reset()
    kp2 = kp.copy()
    kp2[:, 0] = 900.0  # 화면 반대편의 다른 사람
    p2 = PersonPose(keypoints=kp2, bbox=(890, 0, 910, 100))
    out = sm.apply(p2, 11 / 30.0)
    check(abs(out.keypoints[0, 0] - 900.0) < 1.0,
          f"리셋 후 첫 프레임은 그대로 통과해야 함: {out.keypoints[0, 0]:.1f}")


def test_tracker_integration() -> None:
    """트래커 경유 시 스무딩 적용 + grace 초과 이탈 시 리셋."""
    rng = random.Random(7)
    tr = PrimarySubjectTracker(grace_frames=3, smoothing=True)
    kp = np.zeros((33, 3), np.float32)
    kp[:, 2] = 1.0
    outs = []
    for i in range(60):
        k = kp.copy()
        k[:, 0] = 200.0 + rng.gauss(0, 3.0)
        k[:, 1] = 300.0
        p = PersonPose(keypoints=k, bbox=(180, 250, 220, 350))
        out = tr.update([p], now=i / 30.0)
        outs.append(float(out.keypoints[0, 0]))
    check(float(np.std(outs[20:])) < 1.5,
          f"트래커 출력이 스무딩되어야 함: std {np.std(outs[20:]):.2f}")
    # visibility 는 스무딩 대상이 아님
    check(abs(out.keypoints[0, 2] - 1.0) < 1e-6, "visibility 변형 금지")


def main() -> int:
    print("[smoothing]")
    test_jitter_reduction()
    test_fast_motion_lag()
    test_reset_on_new_person()
    test_tracker_integration()
    print("RESULT:", "FAIL" if FAILURES else "OK")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
