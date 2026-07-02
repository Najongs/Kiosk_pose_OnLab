"""2인 실시간 대결 상태머신 (웹 versus.ts 와 동일 로직). 좌=P1, 우=P2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .hold import HoldEvaluator
from .pose_def import PoseDefinition
from .pose_estimator import PersonPose
from .scorer import PoseScorer


class VState(Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    DONE = "done"


@dataclass
class PlayerState:
    present: bool = False
    accuracy: float | None = None
    hold_progress: float = 0.0
    round_done: bool = False
    total: float = 0.0


@dataclass
class VersusState:
    state: VState
    message: str
    pose_index: int
    pose_total: int
    target_pose: PoseDefinition | None = None
    countdown_remaining: float | None = None
    round_remaining: float | None = None
    p1: PlayerState = field(default_factory=PlayerState)
    p2: PlayerState = field(default_factory=PlayerState)
    winner: int | None = None  # 1=P1, 2=P2, 0=무승부, None=진행중


def _center_x(p: PersonPose) -> float:
    return (p.bbox[0] + p.bbox[2]) / 2.0


def assign_players(poses: list[PersonPose]) -> tuple[PersonPose | None, PersonPose | None]:
    if not poses:
        return None, None
    s = sorted(poses, key=_center_x)
    if len(s) == 1:
        return s[0], None
    return s[0], s[-1]


class VersusSession:
    def __init__(self, defs: list[PoseDefinition], scorer: PoseScorer | None = None,
                 pass_accuracy: float = 85.0, countdown_seconds: float = 3.0,
                 round_timeout: float = 15.0):
        if not defs:
            raise ValueError("자세가 하나 이상 필요합니다")
        self.defs = defs
        self.scorer = scorer or PoseScorer()
        self.pass_accuracy = pass_accuracy
        self.countdown_seconds = countdown_seconds
        self.round_timeout = round_timeout
        self.state = VState.IDLE
        self.index = 0
        self.holds: list[HoldEvaluator | None] = [None, None]
        self.done = [False, False]
        self.peak = [0.0, 0.0]
        self.totals = [0.0, 0.0]
        self._deadline: float | None = None
        self._round_deadline: float | None = None

    @property
    def _cur(self) -> PoseDefinition:
        return self.defs[self.index]

    def _new_round(self) -> None:
        hs = self._cur.hold_seconds
        self.holds = [HoldEvaluator(self.pass_accuracy, hs),
                      HoldEvaluator(self.pass_accuracy, hs)]
        self.done = [False, False]
        self.peak = [0.0, 0.0]

    def _player_score(self, pose: PersonPose | None, i: int, now: float) -> PlayerState:
        if pose is None:
            st = self.holds[i].update(0.0, False, now) if self.holds[i] else None
            return PlayerState(False, None, st.progress if st else 0.0,
                               self.done[i], self.totals[i])
        r = self.scorer.score(pose, self._cur)
        st = self.holds[i].update(r.accuracy, r.valid, now)
        self.peak[i] = max(self.peak[i], r.accuracy)
        if st.completed and not self.done[i]:
            self.done[i] = True
            self.totals[i] += st.avg_accuracy
        return PlayerState(True, r.accuracy, st.progress, self.done[i], self.totals[i])

    def update(self, poses: list[PersonPose], now: float) -> VersusState:
        total = len(self.defs)
        a, b = assign_players(poses)
        both = a is not None and b is not None

        if self.state == VState.IDLE:
            if both:
                self.state = VState.COUNTDOWN
                self._deadline = now + self.countdown_seconds
            return VersusState(VState.IDLE,
                               "" if both else "두 명이 카메라 앞에 서 주세요",
                               self.index, total,
                               p1=PlayerState(present=a is not None),
                               p2=PlayerState(present=b is not None))

        if self.state == VState.COUNTDOWN:
            if not both:
                self.state = VState.IDLE
                return VersusState(VState.IDLE, "두 명이 카메라 앞에 서 주세요",
                                   self.index, total)
            rem = max(0.0, (self._deadline or now) - now)
            if rem <= 0:
                self.state = VState.PLAYING
                self.index = 0
                self.totals = [0.0, 0.0]
                self._new_round()
                self._round_deadline = now + self.round_timeout
            else:
                return VersusState(VState.COUNTDOWN, f"'{self._cur.display_name}' 준비",
                                   self.index, total, target_pose=self._cur,
                                   countdown_remaining=rem)

        if self.state == VState.PLAYING:
            p1 = self._player_score(a, 0, now)
            p2 = self._player_score(b, 1, now)
            time_up = now >= (self._round_deadline or now)
            if (self.done[0] and self.done[1]) or time_up:
                if not self.done[0]:
                    self.totals[0] += self.peak[0] * 0.5
                if not self.done[1]:
                    self.totals[1] += self.peak[1] * 0.5
                self.index += 1
                if self.index >= total:
                    self.state = VState.DONE
                    return self._done_state()
                self._new_round()
                self._round_deadline = now + self.round_timeout
            return VersusState(
                VState.PLAYING, self._cur.display_name,
                min(self.index, total - 1), total, target_pose=self._cur,
                round_remaining=max(0.0, (self._round_deadline or now) - now),
                p1=p1, p2=p2)

        return self._done_state()

    def _done_state(self) -> VersusState:
        total = len(self.defs)
        if abs(self.totals[0] - self.totals[1]) < 0.5:
            w = 0
        else:
            w = 1 if self.totals[0] > self.totals[1] else 2
        msg = "무승부!" if w == 0 else f"Player {w} 승리!"
        return VersusState(VState.DONE, msg, total, total,
                           p1=PlayerState(total=self.totals[0]),
                           p2=PlayerState(total=self.totals[1]), winner=w)
