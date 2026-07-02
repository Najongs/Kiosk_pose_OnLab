"""유지시간(hold) + 안정성 판정.

정확도 스트림을 시간과 함께 받아, 목표 정확도(pass_accuracy) 이상을 hold_seconds
동안 유지했는지 판정한다. 짧게 흔들려 아래로 떨어져도 drop_grace 안에 회복하면
유지가 끊기지 않는다. 유지 구간의 평균 정확도를 최종 점수(안정적으로 잘 유지할수록
높음)로 삼는다.

시간(now)은 초 단위 float 로 외부에서 주입한다:
  - 카메라: time.monotonic()
  - 영상: frame_index / fps
  - 테스트: 가짜 증가 클럭
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HoldStatus:
    holding: bool          # 지금 목표를 유지 중인가
    held_time: float       # 현재 연속 유지 시간(초)
    progress: float        # 0~1 (held_time / hold_seconds)
    success: bool          # 이번 업데이트에서 유지 완료가 달성되었는가(1회성 이벤트)
    completed: bool        # 이미 완료 상태인가(성공 이후 유지)
    avg_accuracy: float    # 유지 구간 평균 정확도(최종 점수 후보)


class HoldEvaluator:
    def __init__(self, pass_accuracy: float = 85.0, hold_seconds: float = 3.0,
                 drop_grace: float = 0.4):
        self.pass_accuracy = pass_accuracy
        self.hold_seconds = hold_seconds
        self.drop_grace = drop_grace
        self.reset()

    def reset(self) -> None:
        self._held_time = 0.0
        self._last_now: float | None = None
        self._below_since: float | None = None
        self._acc_sum = 0.0
        self._acc_dt = 0.0
        self._completed = False

    def update(self, accuracy: float, valid: bool, now: float) -> HoldStatus:
        dt = 0.0 if self._last_now is None else max(0.0, now - self._last_now)
        self._last_now = now

        above = valid and accuracy >= self.pass_accuracy

        if above:
            self._below_since = None
            self._held_time += dt
            # 유지 구간 평균 정확도 누적(시간 가중)
            if dt > 0:
                self._acc_sum += accuracy * dt
                self._acc_dt += dt
        else:
            # 목표 아래로 떨어짐: grace 안이면 유지 지속, 넘으면 리셋
            if self._below_since is None:
                self._below_since = now
            if (now - self._below_since) > self.drop_grace:
                self._held_time = 0.0
                self._acc_sum = 0.0
                self._acc_dt = 0.0
                self._completed = False

        newly_success = (not self._completed) and self._held_time >= self.hold_seconds
        if newly_success:
            self._completed = True

        avg_acc = (self._acc_sum / self._acc_dt) if self._acc_dt > 1e-6 else 0.0
        progress = min(1.0, self._held_time / max(self.hold_seconds, 1e-6))
        return HoldStatus(
            holding=above,
            held_time=self._held_time,
            progress=progress,
            success=newly_success,
            completed=self._completed,
            avg_accuracy=avg_acc,
        )
