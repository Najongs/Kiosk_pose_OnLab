"""세션 상태머신.

한 사용자가 자세 세트를 차례로 수행하는 흐름을 관리한다:

  IDLE ──(대상 등장)──▶ COUNTDOWN ──(카운트 0)──▶ SCORING
   ▲                                                  │
   │                                     (유지 성공) │
   │                                                  ▼
  (대상 이탈/전원 완료 후 리셋) ◀── DONE ◀─(마지막) RESULT ─(다음 자세)─▶ COUNTDOWN

update(primary, now) 마다 UI가 그릴 SessionState 스냅샷을 반환한다.
시간(now)은 초 단위 float 로 외부 주입(카메라=monotonic, 영상=frame/fps, 테스트=가짜).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .hold import HoldEvaluator
from .pose_def import PoseDefinition, load_pose
from .pose_estimator import PersonPose
from .report import analyze
from .scorer import PoseScorer, ScoreResult


class State(Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    SCORING = "scoring"
    RESULT = "result"
    DONE = "done"


@dataclass
class SessionState:
    state: State
    message: str
    pose_index: int
    pose_total: int
    target_pose: PoseDefinition | None = None
    accuracy: float | None = None
    score_result: ScoreResult | None = None
    hold_progress: float = 0.0
    countdown_remaining: float | None = None
    last_score: float | None = None
    results: list[tuple[str, float]] = field(default_factory=list)
    final_summary: float | None = None
    report: list[dict] = field(default_factory=list)  # 자세별 유연성 리포트


class Session:
    def __init__(
        self,
        pose_names: list[str],
        scorer: PoseScorer | None = None,
        pass_accuracy: float = 85.0,
        countdown_seconds: float = 3.0,
        result_seconds: float = 3.0,
        lost_timeout: float = 2.0,
    ):
        if not pose_names:
            raise ValueError("자세가 하나 이상 필요합니다")
        self.pose_defs: list[PoseDefinition] = [load_pose(n) for n in pose_names]
        self.scorer = scorer or PoseScorer()
        self.pass_accuracy = pass_accuracy
        self.countdown_seconds = countdown_seconds
        self.result_seconds = result_seconds
        self.lost_timeout = lost_timeout

        self.state = State.IDLE
        self.index = 0
        self.results: list[tuple[str, float]] = []
        self.reports: list[dict] = []
        self._hold: HoldEvaluator | None = None
        self._deadline: float | None = None   # countdown/result 종료 시각
        self._lost_since: float | None = None

    # --- 헬퍼 ---
    @property
    def _current_def(self) -> PoseDefinition:
        return self.pose_defs[self.index]

    def _start_countdown(self, now: float) -> None:
        self.state = State.COUNTDOWN
        self._deadline = now + self.countdown_seconds

    def _start_scoring(self) -> None:
        self.state = State.SCORING
        pd = self._current_def
        self._hold = HoldEvaluator(self.pass_accuracy, pd.hold_seconds)

    def _reset_for_new_user(self) -> None:
        self.state = State.IDLE
        self.index = 0
        self.results = []
        self.reports = []
        self._hold = None
        self._deadline = None
        self._lost_since = None

    # --- 메인 루프 ---
    def update(self, primary: PersonPose | None, now: float) -> SessionState:
        total = len(self.pose_defs)

        if self.state == State.IDLE:
            if primary is not None:
                self._start_countdown(now)
            return SessionState(
                state=State.IDLE,
                message="카메라 앞에 서 주세요",
                pose_index=self.index, pose_total=total,
            )

        if self.state == State.COUNTDOWN:
            if primary is None:
                self.state = State.IDLE
                self._deadline = None
                return SessionState(State.IDLE, "카메라 앞에 서 주세요",
                                    self.index, total)
            remaining = max(0.0, (self._deadline or now) - now)
            pd = self._current_def
            if remaining <= 0:
                self._start_scoring()
            else:
                return SessionState(
                    state=State.COUNTDOWN,
                    message=f"'{pd.display_name}' 준비",
                    pose_index=self.index, pose_total=total,
                    target_pose=pd, countdown_remaining=remaining,
                )

        if self.state == State.SCORING:
            pd = self._current_def
            assert self._hold is not None
            if primary is None:
                # 잠깐 이탈은 grace 로 버티되, 오래 사라지면 처음으로
                if self._lost_since is None:
                    self._lost_since = now
                elif (now - self._lost_since) > self.lost_timeout:
                    self._reset_for_new_user()
                    return SessionState(State.IDLE, "카메라 앞에 서 주세요",
                                        self.index, total)
                status = self._hold.update(0.0, False, now)
                return SessionState(
                    state=State.SCORING,
                    message=f"'{pd.display_name}' — 자세를 잡아 주세요",
                    pose_index=self.index, pose_total=total,
                    target_pose=pd, accuracy=None,
                    hold_progress=status.progress,
                )
            self._lost_since = None
            result = self.scorer.score(primary, pd)
            status = self._hold.update(result.accuracy, result.valid, now)
            if status.success:
                score = status.avg_accuracy
                self.results.append((pd.display_name, score))
                self.reports.append(analyze(primary, pd, result.joint_scores, score))
                self.state = State.RESULT
                self._deadline = now + self.result_seconds
                return SessionState(
                    state=State.RESULT,
                    message=f"완료! {score:.0f}점",
                    pose_index=self.index, pose_total=total,
                    target_pose=pd, accuracy=result.accuracy,
                    score_result=result, hold_progress=1.0,
                    last_score=score, results=list(self.results),
                    report=list(self.reports),
                )
            msg = (f"'{pd.display_name}' 유지 중… {status.held_time:.1f}s"
                   if status.holding else f"'{pd.display_name}' 자세를 맞춰 주세요")
            return SessionState(
                state=State.SCORING,
                message=msg,
                pose_index=self.index, pose_total=total,
                target_pose=pd, accuracy=result.accuracy,
                score_result=result, hold_progress=status.progress,
            )

        if self.state == State.RESULT:
            pd = self._current_def
            if now >= (self._deadline or now):
                self.index += 1
                if self.index >= total:
                    self.state = State.DONE
                    self._deadline = now + self.result_seconds
                elif primary is not None:
                    self._start_countdown(now)
                else:
                    self.state = State.IDLE
            # DONE 으로 전이한 프레임은 done 스냅샷 반환(final_summary 포함)
            if self.state == State.DONE:
                avg = sum(s for _, s in self.results) / len(self.results)
                return SessionState(
                    state=State.DONE,
                    message=f"전체 완료! 평균 {avg:.0f}점",
                    pose_index=total, pose_total=total,
                    results=list(self.results), final_summary=avg,
                    report=list(self.reports),
                )
            return SessionState(
                state=self.state,
                message=(f"완료! {self.results[-1][1]:.0f}점"
                         if self.state == State.RESULT else ""),
                pose_index=min(self.index, total - 1), pose_total=total,
                target_pose=pd if self.state == State.RESULT else None,
                last_score=self.results[-1][1] if self.results else None,
                results=list(self.results),
            )

        # DONE
        avg = sum(s for _, s in self.results) / len(self.results) if self.results else 0.0
        if primary is None and now >= (self._deadline or now):
            self._reset_for_new_user()
            return SessionState(State.IDLE, "카메라 앞에 서 주세요", 0, total)
        return SessionState(
            state=State.DONE,
            message=f"전체 완료! 평균 {avg:.0f}점",
            pose_index=total, pose_total=total,
            results=list(self.results), final_summary=avg,
            report=list(self.reports),
        )
