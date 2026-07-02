"""높이뛰기 측정.

서 있을 때 머리 높이를 기준선으로 잡고(2초 정지 캘리브레이션), 점프 시
머리 키포인트가 얼마나 올라갔는지를 cm 로 근사 환산한다(몸통 길이≈50cm 가정).
단일 정면 카메라 근사치이므로 "약 N cm" 로 표기할 것.

  IDLE ─▶ CALIBRATE(정지 2s) ─▶ READY ─(상승 감지)▶ JUMP ─(착지)▶ REST ─▶ … ─▶ DONE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import median

from core.pose_estimator import PersonPose

from .common import head_y, torso_len_px


class JState(Enum):
    IDLE = "idle"
    CALIBRATE = "calibrate"
    READY = "ready"
    JUMP = "jump"
    REST = "rest"
    DONE = "done"


TORSO_CM = 50.0          # 성인 몸통(어깨중점~엉덩이중점) 근사 길이
LAUNCH_CM = 8.0          # 이 이상 올라가면 점프 시작으로 판정
LAND_CM = 4.0            # 기준선 근처로 돌아오면 착지로 판정
CALIB_JITTER_CM = 5.0    # 캘리브레이션 중 이 이상 흔들리면 재시도
SCORE_FULL_CM = 40.0     # 이 높이면 100점


@dataclass
class JumpState:
    state: JState
    message: str
    attempt_index: int
    attempt_total: int
    baseline_head_y: float | None = None
    target_line_y: float | None = None
    current_head_y: float | None = None
    cm_per_px: float | None = None
    target_cm: float = 30.0
    last_cm: float | None = None
    best_cm: float | None = None
    attempts_cm: list[float] = field(default_factory=list)
    calib_progress: float = 0.0
    score: float | None = None


class JumpGame:
    REST_SECONDS = 2.0
    LOST_TIMEOUT = 2.0

    def __init__(self, attempts: int = 3, calib_seconds: float = 2.0,
                 target_cm: float = 30.0):
        self.attempts = max(1, int(attempts))
        self.calib_seconds = float(calib_seconds)
        self.target_cm = float(target_cm)
        self._reset()

    def _reset(self) -> None:
        self.state = JState.IDLE
        self.attempt_index = 0
        self.attempts_cm: list[float] = []
        self.baseline: float | None = None
        self.cm_per_px: float | None = None
        self._samples: list[float] = []
        self._torsos: list[float] = []
        self._calib_start: float | None = None
        self._peak: float | None = None
        self._last_cm: float | None = None
        self._deadline: float | None = None
        self._lost_since: float | None = None

    def _snap(self, message: str, hy: float | None = None, **kw) -> JumpState:
        best = max(self.attempts_cm) if self.attempts_cm else None
        tline = None
        if self.baseline is not None and self.cm_per_px:
            tline = self.baseline - self.target_cm / self.cm_per_px
        return JumpState(
            state=self.state, message=message,
            attempt_index=self.attempt_index, attempt_total=self.attempts,
            baseline_head_y=self.baseline, target_line_y=tline,
            current_head_y=hy, cm_per_px=self.cm_per_px,
            target_cm=self.target_cm, last_cm=self._last_cm, best_cm=best,
            attempts_cm=list(self.attempts_cm), **kw)

    def _score(self) -> float:
        best = max(self.attempts_cm) if self.attempts_cm else 0.0
        return max(0.0, min(100.0, best / SCORE_FULL_CM * 100.0))

    def _start_calib(self, now: float) -> None:
        self.state = JState.CALIBRATE
        self._samples = []
        self._torsos = []
        self._calib_start = now

    def update(self, primary: PersonPose | None, now: float) -> JumpState:
        if primary is None:
            if self.state == JState.DONE:
                return self._snap(f"최고 약 {max(self.attempts_cm or [0]):.0f}cm!",
                                  score=self._score())
            if self.state == JState.IDLE:
                return self._snap("카메라 앞에 서 주세요")
            if self._lost_since is None:
                self._lost_since = now
            elif now - self._lost_since > self.LOST_TIMEOUT:
                self._reset()
                return self._snap("카메라 앞에 서 주세요")
            return self._snap("화면 안으로 들어와 주세요")
        self._lost_since = None

        hy = head_y(primary)

        if self.state == JState.IDLE:
            self._start_calib(now)
            return self._snap("가만히 서 주세요 — 기준 높이 측정 중", hy)

        if self.state == JState.CALIBRATE:
            torso = torso_len_px(primary)
            if hy is not None and torso is not None:
                self._samples.append(hy)
                self._torsos.append(torso)
            elapsed = now - (self._calib_start if self._calib_start is not None
                             else now)
            prog = min(1.0, elapsed / self.calib_seconds)
            if elapsed >= self.calib_seconds:
                if len(self._samples) < 5:
                    self._start_calib(now)
                    return self._snap("머리가 잘 보이게 서 주세요", hy)
                cm_per_px = TORSO_CM / max(1e-6, median(self._torsos))
                spread = (max(self._samples) - min(self._samples)) * cm_per_px
                if spread > CALIB_JITTER_CM:
                    self._start_calib(now)
                    return self._snap("가만히 서 주세요 — 다시 측정합니다", hy)
                self.baseline = median(self._samples)
                self.cm_per_px = cm_per_px
                self.state = JState.READY
                return self._snap("준비 완료 — 힘껏 점프!", hy)
            return self._snap("가만히 서 주세요 — 기준 높이 측정 중", hy,
                              calib_progress=prog)

        if self.state == JState.READY:
            if hy is not None and self.baseline is not None and self.cm_per_px:
                if (self.baseline - hy) * self.cm_per_px >= LAUNCH_CM:
                    self.state = JState.JUMP
                    self._peak = hy
                    return self._snap("점프!", hy)
            return self._snap(f"{self.attempt_index + 1}번째 시도 — 힘껏 점프!", hy)

        if self.state == JState.JUMP:
            if hy is not None:
                self._peak = min(self._peak if self._peak is not None else hy, hy)
                assert self.baseline is not None and self.cm_per_px
                if (self.baseline - hy) * self.cm_per_px <= LAND_CM:  # 착지
                    peak = self._peak if self._peak is not None else hy
                    cm = (self.baseline - peak) * self.cm_per_px
                    self._last_cm = cm
                    self.attempts_cm.append(cm)
                    self.state = JState.REST
                    self._deadline = now + self.REST_SECONDS
                    return self._snap(f"약 {cm:.0f}cm!", hy)
            return self._snap("점프!", hy)

        if self.state == JState.REST:
            if self._deadline is not None and now >= self._deadline:
                self.attempt_index += 1
                if self.attempt_index >= self.attempts:
                    self.state = JState.DONE
                else:
                    self.state = JState.READY
                    return self._snap(f"{self.attempt_index + 1}번째 시도 — 힘껏 점프!", hy)
            else:
                return self._snap(f"약 {self._last_cm:.0f}cm!" if self._last_cm else "",
                                  hy)

        # DONE
        best = max(self.attempts_cm) if self.attempts_cm else 0.0
        return self._snap(f"완료! 최고 약 {best:.0f}cm", hy, score=self._score())
