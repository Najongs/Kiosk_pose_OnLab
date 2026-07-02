"""팔굽혀펴기 검사.

팔꿈치 각도의 위(펴짐)→아래(굽힘)→위 전이로 개수를 세고, 어깨-엉덩이-발목
일직선 각도로 자세 품질(허리 처짐/들림)을 피드백한다.
정면보다 측면(비스듬히)에서 정확 — UI 에 안내 문구를 표시할 것.

  IDLE ─(사람+팔각도 감지)▶ COUNTING ─(시간 종료/목표 달성)▶ DONE
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.pose_estimator import PersonPose

from .common import body_line_angle, elbow_angle


class PState(Enum):
    IDLE = "idle"
    COUNTING = "counting"
    DONE = "done"


POSTURE_MIN_ANGLE = 160.0  # 어깨-엉덩이-발목 이보다 굽으면 자세 경고


@dataclass
class PushupState:
    state: PState
    message: str
    reps: int = 0
    good_reps: int = 0
    elbow_angle: float | None = None
    phase: str = "up"            # "up" | "down"
    posture_ok: bool = True
    posture_msg: str = ""
    time_remaining: float | None = None
    target_reps: int = 15
    mode: str = "timed"
    up_angle: float = 150.0    # 렌더러 게이지가 카운트 기준과 같은 눈금을 쓰도록
    down_angle: float = 95.0
    score: float | None = None
    quality: float | None = None  # 자세 양호 rep 비율 (0~1)


class PushupGame:
    LOST_TIMEOUT = 3.0  # 팔굽혀펴기는 프레임 아웃이 잦아 여유 있게

    def __init__(self, mode: str = "timed", duration: float = 30.0,
                 target_reps: int = 15, up_angle: float = 150.0,
                 down_angle: float = 95.0):
        self.mode = mode if mode in ("timed", "target") else "timed"
        self.duration = float(duration)
        self.target_reps = max(1, int(target_reps))
        self.up_angle = float(up_angle)
        self.down_angle = float(down_angle)
        self._reset()

    def _reset(self) -> None:
        self.state = PState.IDLE
        self.reps = 0
        self.good_reps = 0
        self.phase = "up"
        self._down_was_good = True
        self._start: float | None = None
        self._lost_since: float | None = None

    def _snap(self, message: str, **kw) -> PushupState:
        return PushupState(state=self.state, message=message, reps=self.reps,
                           good_reps=self.good_reps, phase=self.phase,
                           target_reps=self.target_reps, mode=self.mode,
                           up_angle=self.up_angle, down_angle=self.down_angle,
                           **kw)

    def _quality(self) -> float:
        return self.good_reps / self.reps if self.reps else 1.0

    def _score(self) -> float:
        base = min(100.0, self.reps / self.target_reps * 100.0)
        return max(0.0, min(100.0, base * (0.7 + 0.3 * self._quality())))

    def _finish_kw(self) -> dict:
        return {"score": self._score(), "quality": self._quality()}

    def update(self, primary: PersonPose | None, now: float) -> PushupState:
        if primary is None:
            if self.state == PState.DONE:
                return self._snap(f"완료! {self.reps}개", **self._finish_kw())
            if self.state == PState.IDLE:
                return self._snap("팔굽혀펴기 자세를 잡아 주세요 (측면 권장)")
            if self._lost_since is None:
                self._lost_since = now
            elif now - self._lost_since > self.LOST_TIMEOUT:
                self._reset()
                return self._snap("팔굽혀펴기 자세를 잡아 주세요 (측면 권장)")
            return self._snap("화면 안으로 들어와 주세요",
                              time_remaining=self._remaining(now))
        self._lost_since = None

        ang = elbow_angle(primary)
        body = body_line_angle(primary)
        posture_ok = body is None or body >= POSTURE_MIN_ANGLE
        posture_msg = "" if posture_ok else "허리를 곧게 펴 주세요"

        if self.state == PState.IDLE:
            if ang is None:
                return self._snap("팔이 잘 보이게 자세를 잡아 주세요")
            self.state = PState.COUNTING
            self._start = now
            return self._snap("시작! 팔을 굽혔다 펴세요", elbow_angle=ang,
                              posture_ok=posture_ok, posture_msg=posture_msg,
                              time_remaining=self._remaining(now))

        if self.state == PState.COUNTING:
            if ang is not None:
                if self.phase == "up" and ang <= self.down_angle:
                    self.phase = "down"
                    self._down_was_good = posture_ok
                elif self.phase == "down":
                    if not posture_ok:
                        self._down_was_good = False
                    if ang >= self.up_angle:  # 한 개 완료
                        self.phase = "up"
                        self.reps += 1
                        if self._down_was_good:
                            self.good_reps += 1
            remaining = self._remaining(now)
            done = ((self.mode == "timed" and remaining is not None and remaining <= 0)
                    or (self.mode == "target" and self.reps >= self.target_reps))
            if done:
                self.state = PState.DONE
                return self._snap(f"완료! {self.reps}개", elbow_angle=ang,
                                  time_remaining=0.0 if self.mode == "timed" else None,
                                  **self._finish_kw())
            msg = posture_msg or (f"{self.reps}개 — 계속!" if self.reps else
                                  "팔을 굽혔다 펴세요")
            return self._snap(msg, elbow_angle=ang, posture_ok=posture_ok,
                              posture_msg=posture_msg, time_remaining=remaining)

        # DONE
        return self._snap(f"완료! {self.reps}개", elbow_angle=ang,
                          **self._finish_kw())

    def _remaining(self, now: float) -> float | None:
        if self.mode != "timed" or self._start is None:
            return self.duration if self.mode == "timed" else None
        return max(0.0, self.duration - (now - self._start))
