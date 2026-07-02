"""미니게임 로직 헤드리스 테스트 — 합성 PersonPose + 가짜 시간으로 상태 전이 검증.

실행: python tools/test_games.py  →  RESULT: OK / FAIL
(카메라·Qt·모델 불필요. verify_ui.py 와 같은 스크립트 관례.)
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core.games.jump import JState, JumpGame
from core.games.pushup import PState, PushupGame
from core.games.reaction import ReactionGame, RState
from core.pose_estimator import (
    LEFT_ANKLE, LEFT_ELBOW, LEFT_HIP, LEFT_SHOULDER, LEFT_WRIST, NOSE,
    RIGHT_ANKLE, RIGHT_ELBOW, RIGHT_HIP, RIGHT_SHOULDER, RIGHT_WRIST,
    PersonPose,
)

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"  FAIL: {msg}")


def make_pose(head_y: float = 100.0, hands_up: bool = False,
              elbow_deg_bent: bool = False, hips_sag: bool = False) -> PersonPose:
    """서 있는 사람 골격 (픽셀 좌표, 어깨폭 100px, 몸통 150px)."""
    kp = np.zeros((33, 3), dtype=np.float32)

    def put(i, x, y):
        kp[i] = (x, y, 1.0)

    sh_y = head_y + 60
    hip_y = sh_y + 150
    put(NOSE, 300, head_y)
    put(LEFT_SHOULDER, 250, sh_y)
    put(RIGHT_SHOULDER, 350, sh_y)
    put(LEFT_HIP, 270, hip_y)
    put(RIGHT_HIP, 330, hip_y)
    put(LEFT_ANKLE, 270 if not hips_sag else 200, hip_y + 220)
    put(RIGHT_ANKLE, 330 if not hips_sag else 260, hip_y + 220)
    if hands_up:
        put(LEFT_WRIST, 240, sh_y - 120)
        put(RIGHT_WRIST, 360, sh_y - 120)
        put(LEFT_ELBOW, 245, sh_y - 60)
        put(RIGHT_ELBOW, 355, sh_y - 60)
    elif elbow_deg_bent:  # 팔꿈치 직각 굽힘 (팔굽혀펴기 down)
        put(LEFT_ELBOW, 250, sh_y + 70)
        put(RIGHT_ELBOW, 350, sh_y + 70)
        put(LEFT_WRIST, 180, sh_y + 70)
        put(RIGHT_WRIST, 420, sh_y + 70)
    else:  # 팔 곧게 내림 (up)
        put(LEFT_ELBOW, 250, sh_y + 75)
        put(RIGHT_ELBOW, 350, sh_y + 75)
        put(LEFT_WRIST, 250, sh_y + 150)
        put(RIGHT_WRIST, 350, sh_y + 150)
    return PersonPose(keypoints=kp, bbox=(200, head_y, 400, hip_y + 230))


def test_reaction() -> None:
    print("[reaction]")
    g = ReactionGame(rounds=3, min_delay=1.0, max_delay=2.0,
                     rng=random.Random(42))
    down, up = make_pose(), make_pose(hands_up=True)
    t = 0.0
    st = g.update(down, t)
    check(st.state == RState.WAIT, f"IDLE→WAIT 여야 함: {st.state}")

    # false start: 신호 전에 손 들기
    t += 0.1
    st = g.update(up, t)
    check(st.state == RState.REST and st.false_start, "false start 감지 실패")
    check(st.false_starts == 1, "false_starts 카운트 실패")

    # 라운드 3개 정상 수행 (REST→WAIT 재무장 → 신호까지 대기 → 손들기)
    for _ in range(3):
        for _ in range(600):  # 최대 60s 시뮬레이션
            t += 0.1
            hands = up if st.signal_on else down
            st = g.update(hands, t)
            if st.state in (RState.DONE,) or (st.state == RState.REST
                                              and st.last_ms is not None):
                break
        if st.state == RState.DONE:
            break
    while st.state != RState.DONE:
        t += 0.1
        st = g.update(down, t)
        if t > 120:
            break
    check(st.state == RState.DONE, f"DONE 도달 실패: {st.state}")
    check(len(st.times_ms) == 3, f"기록 3개여야 함: {st.times_ms}")
    check(all(0 < ms <= 2000 for ms in st.times_ms), f"ms 범위 오류: {st.times_ms}")
    check(st.score is not None and 0 <= st.score <= 100, f"score 오류: {st.score}")

    # 시간 초과: 신호 후 손을 안 들면 상한 기록 + timed_out 플래그 (성공음 방지용)
    gt = ReactionGame(rounds=1, min_delay=0.5, max_delay=0.5,
                      rng=random.Random(1))
    t2 = 0.0
    st = gt.update(down, t2)
    while st.state != RState.REST and t2 < 10:
        t2 += 0.1
        st = gt.update(down, t2)
    check(st.state == RState.REST and st.timed_out and not st.false_start,
          f"시간 초과 플래그 오류: {st.state} timed_out={st.timed_out}")
    check(st.last_ms == 2000.0, f"상한 기록이어야 함: {st.last_ms}")

    # rng 주입 → 결정적
    g2 = ReactionGame(rounds=3, min_delay=1.0, max_delay=2.0,
                      rng=random.Random(7))
    g3 = ReactionGame(rounds=3, min_delay=1.0, max_delay=2.0,
                      rng=random.Random(7))
    g2.update(down, 0.0)
    g3.update(down, 0.0)
    check(g2._signal_at == g3._signal_at, "같은 시드 → 같은 신호 시각이어야 함")


def test_jump() -> None:
    print("[jump]")
    g = JumpGame(attempts=2, calib_seconds=1.0, target_cm=30.0)
    stand = make_pose(head_y=100.0)
    t = 0.0
    st = g.update(stand, t)
    check(st.state == JState.CALIBRATE, f"IDLE→CALIBRATE 여야 함: {st.state}")
    for _ in range(12):
        t += 0.1
        st = g.update(stand, t)
    check(st.state == JState.READY, f"캘리브레이션 후 READY 여야 함: {st.state}")
    check(st.baseline_head_y is not None and abs(st.baseline_head_y - 100) < 1,
          f"기준선 오류: {st.baseline_head_y}")
    # 몸통 150px = 50cm → cm_per_px = 1/3. 30cm 점프 = 90px 상승
    check(st.cm_per_px is not None and abs(st.cm_per_px - 1 / 3) < 0.01,
          f"cm_per_px 오류: {st.cm_per_px}")

    for _ in range(2):  # 두 번 점프 (90px = 약 30cm)
        for dy in (40, 90, 90, 40, 0):
            t += 0.1
            st = g.update(make_pose(head_y=100.0 - dy), t)
        check(st.last_cm is not None and abs(st.last_cm - 30.0) < 2.0,
              f"점프 높이 오류: {st.last_cm}")
        for _ in range(25):
            t += 0.1
            st = g.update(stand, t)
            if st.state in (JState.READY, JState.DONE):
                break
    check(st.state == JState.DONE, f"DONE 도달 실패: {st.state}")
    check(st.best_cm is not None and abs(st.best_cm - 30.0) < 2.0,
          f"best_cm 오류: {st.best_cm}")
    check(st.score is not None and 70 <= st.score <= 80,
          f"30cm→75점 근처여야 함: {st.score}")


def test_pushup() -> None:
    print("[pushup]")
    g = PushupGame(mode="target", target_reps=3)
    up, down = make_pose(), make_pose(elbow_deg_bent=True)
    t = 0.0
    st = g.update(up, t)
    check(st.state == PState.COUNTING, f"IDLE→COUNTING 여야 함: {st.state}")
    for _ in range(3):
        t += 0.5
        st = g.update(down, t)
        t += 0.5
        st = g.update(up, t)
    check(st.state == PState.DONE, f"3개 후 DONE 여야 함: {st.state}")
    check(st.reps == 3, f"reps=3 이어야 함: {st.reps}")
    check(st.good_reps == 3, f"good_reps=3 이어야 함: {st.good_reps}")
    check(st.score == 100.0, f"만점이어야 함: {st.score}")

    # timed 모드 + 시간 종료
    g2 = PushupGame(mode="timed", duration=5.0, target_reps=10)
    t = 0.0
    st = g2.update(up, t)
    t += 0.5
    st = g2.update(down, t)
    t += 0.5
    st = g2.update(up, t)
    check(st.reps == 1, f"1개 세어야 함: {st.reps}")
    st = g2.update(up, 6.0)
    check(st.state == PState.DONE, f"시간 종료 후 DONE: {st.state}")
    check(st.time_remaining == 0.0, f"time_remaining=0: {st.time_remaining}")

    # 허리 처진 자세 → rep 은 세되 good_rep 아님 + 경고 메시지
    g3 = PushupGame(mode="target", target_reps=1)
    bad_down = make_pose(elbow_deg_bent=True, hips_sag=True)
    g3.update(up, 0.0)
    st = g3.update(bad_down, 0.5)
    check(not st.posture_ok and st.posture_msg, f"자세 경고 없음: {st.posture_msg!r}")
    st = g3.update(up, 1.0)
    check(st.reps == 1 and st.good_reps == 0,
          f"나쁜 자세 rep 품질 분리 실패: reps={st.reps} good={st.good_reps}")
    check(st.quality == 0.0, f"quality=0 이어야 함: {st.quality}")


def main() -> int:
    test_reaction()
    test_jump()
    test_pushup()
    if FAILURES:
        print(f"RESULT: FAIL ({len(FAILURES)})")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
