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


def _area(p: PersonPose) -> float:
    x1, y1, x2, y2 = p.bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _iou(a: tuple, b: tuple) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / max(1e-6, area_a + area_b - inter)


def dedupe_poses(poses: list[PersonPose], iou_thresh: float = 0.45) -> list[PersonPose]:
    """같은 사람이 두 번 검출되는 경우 제거 — 많이 겹치면 큰 검출 하나만 남긴다."""
    out: list[PersonPose] = []
    for p in sorted(poses, key=_area, reverse=True):
        if all(_iou(p.bbox, q.bbox) < iou_thresh for q in out):
            out.append(p)
    return out


def assign_players(poses: list[PersonPose],
                   frame_w: float | None = None) -> tuple[PersonPose | None, PersonPose | None]:
    """좌반=P1, 우반=P2. frame_w 를 주면 화면 절반 기준으로 고정 배정한다 —
    혼자 오른쪽에 서 있으면 P2 로 잡히고, 왼쪽 사람이 P2 가 되는 일이 없다.
    같은 반쪽에 여러 명이면 가장 큰(가까운) 사람을 쓴다."""
    poses = dedupe_poses(poses)
    if not poses:
        return None, None
    if frame_w:
        mid = frame_w / 2.0
        left = [p for p in poses if _center_x(p) < mid]
        right = [p for p in poses if _center_x(p) >= mid]
        a = max(left, key=_area) if left else None
        b = max(right, key=_area) if right else None
        return a, b
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

    def update(self, poses: list[PersonPose], now: float,
               frame_w: float | None = None) -> VersusState:
        total = len(self.defs)
        a, b = assign_players(poses, frame_w)
        both = a is not None and b is not None

        if self.state == VState.IDLE:
            if both:
                self.state = VState.COUNTDOWN
                self._deadline = now + self.countdown_seconds
            one_side = (a is None) != (b is None)
            msg = ("" if both else
                   "한 명씩 화면 왼쪽/오른쪽에 서 주세요" if one_side else
                   "두 명이 카메라 앞에 서 주세요")
            return VersusState(VState.IDLE, msg,
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
