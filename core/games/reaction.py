"""반응속도 테스트.

신호(화면 플래시)가 뜨면 최대한 빨리 손을 드는 게임. 버튼 없이 포즈로 판정.

  IDLE ──(사람+손내림)──▶ WAIT(무작위 대기) ──(신호)──▶ SIGNAL ──(손들기)──▶ REST
   ▲                        │ (미리 들면 false start → REST 후 재시도)      │
   └───(이탈)────────────── DONE ◀──(라운드 소진)──────────────────────────┘

측정 ms 에는 카메라·추론 지연(~100ms+)이 포함되므로 절대값보다 경쟁용 상대값.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from core.pose_estimator import PersonPose

from .common import wrist_above_shoulder


class RState(Enum):
    IDLE = "idle"
    WAIT = "wait"        # 신호 대기 (아직 손 들면 안 됨)
    SIGNAL = "signal"    # 신호 켜짐 — 손 들기!
    REST = "rest"        # 라운드 결과 표시
    DONE = "done"


@dataclass
class ReactionState:
    state: RState
    message: str
    round_index: int
    round_total: int
    signal_on: bool = False
    last_ms: float | None = None
    times_ms: list[float] = field(default_factory=list)
    best_ms: float | None = None
    avg_ms: float | None = None
    false_start: bool = False
    false_starts: int = 0
    timed_out: bool = False   # 직전 라운드가 무반응 시간 초과였는지
    score: float | None = None


class ReactionGame:
    REACT_TIMEOUT = 2.0     # 신호 후 이 시간 내 반응 없으면 그 라운드는 상한 기록
    REST_SECONDS = 1.6
    LOST_TIMEOUT = 2.0
    FALSE_PENALTY = 5.0     # false start 1회당 감점

    def __init__(self, rounds: int = 5, min_delay: float = 1.5,
                 max_delay: float = 4.0, rng: random.Random | None = None):
        self.rounds = max(1, int(rounds))
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.rng = rng or random.Random()
        self._reset()

    def _reset(self) -> None:
        self.state = RState.IDLE
        self.round_index = 0
        self.times_ms: list[float] = []
        self.false_starts = 0
        self._signal_at: float | None = None
        self._signal_shown: float | None = None
        self._deadline: float | None = None
        self._last_ms: float | None = None
        self._was_false = False
        self._was_timeout = False
        self._lost_since: float | None = None

    def _arm(self, now: float) -> None:
        self.state = RState.WAIT
        self._signal_at = now + self.rng.uniform(self.min_delay, self.max_delay)
        self._was_false = False

    def _record(self, ms: float, now: float, timeout: bool = False) -> None:
        """라운드 기록 + REST 진입 (round_index = 완료한 라운드 수)."""
        self.times_ms.append(ms)
        self._last_ms = ms
        self._was_timeout = timeout
        self.round_index += 1
        self.state = RState.REST
        self._deadline = now + self.REST_SECONDS

    def _snap(self, message: str, **kw) -> ReactionState:
        avg = (sum(self.times_ms) / len(self.times_ms)) if self.times_ms else None
        best = min(self.times_ms) if self.times_ms else None
        return ReactionState(
            state=self.state, message=message,
            round_index=self.round_index, round_total=self.rounds,
            times_ms=list(self.times_ms), last_ms=self._last_ms,
            best_ms=best, avg_ms=avg, false_starts=self.false_starts,
            timed_out=self._was_timeout, **kw)

    def _score(self) -> float:
        if not self.times_ms:
            return 0.0
        avg = sum(self.times_ms) / len(self.times_ms)
        base = 100.0 - max(0.0, avg - 300.0) / 8.0  # 300ms(지연 포함)까지 만점
        return max(0.0, min(100.0, base - self.false_starts * self.FALSE_PENALTY))

    def update(self, primary: PersonPose | None, now: float) -> ReactionState:
        # 대상 이탈 처리 — 진행 중 오래 사라지면 처음부터
        if primary is None:
            if self.state in (RState.IDLE, RState.DONE):
                if self.state == RState.DONE:
                    return self._snap(f"평균 {self._fmt_avg()} — 참여해 보세요!",
                                      score=self._score())
                return self._snap("카메라 앞에 서 주세요")
            if self._lost_since is None:
                self._lost_since = now
            elif now - self._lost_since > self.LOST_TIMEOUT:
                self._reset()
                return self._snap("카메라 앞에 서 주세요")
            return self._snap("화면 안으로 들어와 주세요")
        self._lost_since = None

        if self.state == RState.IDLE:
            if wrist_above_shoulder(primary):
                return self._snap("손을 내리면 시작합니다")
            self._arm(now)
            return self._snap("신호가 뜨면 손을 번쩍!", false_start=False)

        if self.state == RState.WAIT:
            if wrist_above_shoulder(primary):  # 미리 들었다 — false start
                self.false_starts += 1
                self._was_false = True
                self._was_timeout = False
                self._last_ms = None
                self.state = RState.REST
                self._deadline = now + self.REST_SECONDS
                return self._snap("너무 빨라요! 신호를 기다리세요", false_start=True)
            if self._signal_at is not None and now >= self._signal_at:
                self.state = RState.SIGNAL
                self._signal_shown = now
                return self._snap("지금! 손을 드세요!", signal_on=True)
            return self._snap("잠깐… 기다리세요")

        if self.state == RState.SIGNAL:
            elapsed = now - (self._signal_shown
                             if self._signal_shown is not None else now)
            if wrist_above_shoulder(primary):
                ms = elapsed * 1000.0
                self._record(ms, now)
                return self._snap(f"{ms:.0f}ms!", signal_on=False)
            if elapsed >= self.REACT_TIMEOUT:  # 무반응 — 상한 기록 후 진행
                self._record(self.REACT_TIMEOUT * 1000.0, now, timeout=True)
                return self._snap("시간 초과!", signal_on=False)
            return self._snap("지금! 손을 드세요!", signal_on=True)

        if self.state == RState.REST:
            if self._deadline is not None and now >= self._deadline:
                if self.round_index >= self.rounds:
                    self.state = RState.DONE
                elif wrist_above_shoulder(primary):
                    return self._snap("손을 내려 주세요")  # 내려야 다음 라운드
                else:
                    self._arm(now)
                    return self._snap("신호가 뜨면 손을 번쩍!")
            if self.state != RState.DONE:
                msg = ("너무 빨라요! 다시 갑니다" if self._was_false
                       else "시간 초과!" if self._was_timeout
                       else f"{self._last_ms:.0f}ms!" if self._last_ms else "")
                return self._snap(msg, false_start=self._was_false)

        # DONE
        return self._snap(f"완료! 평균 {self._fmt_avg()}", score=self._score())

    def _fmt_avg(self) -> str:
        if not self.times_ms:
            return "기록 없음"
        return f"{sum(self.times_ms) / len(self.times_ms):.0f}ms"
