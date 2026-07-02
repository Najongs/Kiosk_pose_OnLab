/** 세션 상태머신 — 파이썬 core/session.py 와 동일 흐름. now 는 초 단위. */

import { HoldEvaluator } from "./hold";
import { PersonPose } from "./keypoints";
import { PoseDefinition } from "./poseDef";
import { PoseScorer, ScoreResult } from "./scorer";
import { analyze, PoseReport } from "./report";

export type State = "idle" | "countdown" | "scoring" | "result" | "done";

export interface SessionState {
  state: State;
  message: string;
  poseIndex: number;
  poseTotal: number;
  targetPose: PoseDefinition | null;
  accuracy: number | null;
  scoreResult: ScoreResult | null;
  holdProgress: number;
  countdownRemaining: number | null;
  lastScore: number | null;
  results: [string, number][];
  finalSummary: number | null;
  report: PoseReport[];
  combo: number;       // 연속 합격 콤보
  comboBonus: number;  // 이번 자세에 붙은 콤보 보너스 점수
}

/** 콤보 보너스: 2연속부터 +2점씩, 최대 +10점 (파이썬 Session.combo_bonus 동일) */
export function comboBonus(combo: number): number {
  return Math.min(10, Math.max(0, combo - 1) * 2);
}

function blank(state: State, message: string, idx: number, total: number): SessionState {
  return {
    state, message, poseIndex: idx, poseTotal: total,
    targetPose: null, accuracy: null, scoreResult: null,
    holdProgress: 0, countdownRemaining: null, lastScore: null,
    results: [], finalSummary: null, report: [], combo: 0, comboBonus: 0,
  };
}

export class Session {
  private state: State = "idle";
  private index = 0;
  private results: [string, number][] = [];
  private reports: PoseReport[] = [];
  private hold: HoldEvaluator | null = null;
  private deadline: number | null = null;
  private lostSince: number | null = null;
  private combo = 0;
  private lastBonus = 0;

  constructor(
    private poseDefs: PoseDefinition[],
    private scorer: PoseScorer,
    private passAccuracy = 85,
    private countdownSeconds = 3,
    private resultSeconds = 3,
    private lostTimeout = 2,
  ) {
    if (poseDefs.length === 0) throw new Error("자세가 하나 이상 필요합니다");
  }

  private get curDef(): PoseDefinition {
    return this.poseDefs[this.index];
  }

  private startCountdown(now: number): void {
    this.state = "countdown";
    this.deadline = now + this.countdownSeconds;
  }
  private startScoring(): void {
    this.state = "scoring";
    this.hold = new HoldEvaluator(this.passAccuracy, this.curDef.hold_seconds ?? 3);
  }
  private resetForNewUser(): void {
    this.state = "idle";
    this.index = 0;
    this.results = [];
    this.reports = [];
    this.hold = null;
    this.deadline = null;
    this.lostSince = null;
    this.combo = 0;
    this.lastBonus = 0;
  }

  update(primary: PersonPose | null, now: number): SessionState {
    const total = this.poseDefs.length;

    if (this.state === "idle") {
      if (primary !== null) this.startCountdown(now);
      return blank("idle", "카메라 앞에 서 주세요", this.index, total);
    }

    if (this.state === "countdown") {
      if (primary === null) {
        this.state = "idle";
        this.deadline = null;
        return blank("idle", "카메라 앞에 서 주세요", this.index, total);
      }
      const remaining = Math.max(0, (this.deadline ?? now) - now);
      const pd = this.curDef;
      if (remaining <= 0) {
        this.startScoring();
      } else {
        const st = blank("countdown", `'${pd.display_name}' 준비`, this.index, total);
        st.targetPose = pd;
        st.countdownRemaining = remaining;
        return st;
      }
    }

    if (this.state === "scoring") {
      const pd = this.curDef;
      const hold = this.hold!;
      if (primary === null) {
        if (this.lostSince === null) this.lostSince = now;
        else if (now - this.lostSince > this.lostTimeout) {
          this.resetForNewUser();
          return blank("idle", "카메라 앞에 서 주세요", this.index, total);
        }
        const status = hold.update(0, false, now);
        const st = blank("scoring", `'${pd.display_name}' — 자세를 잡아 주세요`, this.index, total);
        st.targetPose = pd;
        st.holdProgress = status.progress;
        return st;
      }
      this.lostSince = null;
      const result = this.scorer.score(primary, pd);
      const status = hold.update(result.accuracy, result.valid, now);
      if (status.success) {
        this.combo += 1;
        this.lastBonus = comboBonus(this.combo);
        const score = Math.min(100, status.avgAccuracy + this.lastBonus);
        this.results.push([pd.display_name, score]);
        this.reports.push(analyze(primary, pd, result.jointScores, score));
        this.state = "result";
        this.deadline = now + this.resultSeconds;
        const st = blank("result", `완료! ${Math.round(score)}점`, this.index, total);
        st.targetPose = pd;
        st.accuracy = result.accuracy;
        st.scoreResult = result;
        st.holdProgress = 1;
        st.lastScore = score;
        st.results = [...this.results];
        st.report = [...this.reports];
        st.combo = this.combo;
        st.comboBonus = this.lastBonus;
        return st;
      }
      const msg = status.holding
        ? `'${pd.display_name}' 유지 중… ${status.heldTime.toFixed(1)}s`
        : `'${pd.display_name}' 자세를 맞춰 주세요`;
      const st = blank("scoring", msg, this.index, total);
      st.targetPose = pd;
      st.accuracy = result.accuracy;
      st.scoreResult = result;
      st.holdProgress = status.progress;
      st.combo = this.combo;
      return st;
    }

    if (this.state === "result") {
      const pd = this.curDef;
      if (now >= (this.deadline ?? now)) {
        this.index += 1;
        if (this.index >= total) {
          this.state = "done";
          this.deadline = now + this.resultSeconds;
        } else if (primary !== null) {
          this.startCountdown(now);
        } else {
          this.state = "idle";
        }
      }
      // done 으로 전이한 프레임은 done 스냅샷을 반환(finalSummary 포함)
      if (this.state === "done") {
        const avg = this.results.reduce((s, [, v]) => s + v, 0) / this.results.length;
        const st = blank("done", `전체 완료! 평균 ${Math.round(avg)}점`, total, total);
        st.results = [...this.results];
        st.finalSummary = avg;
        st.report = [...this.reports];
        return st;
      }
      const st = blank(
        "result",
        `완료! ${Math.round(this.results[this.results.length - 1][1])}점`,
        Math.min(this.index, total - 1),
        total,
      );
      st.targetPose = pd;
      st.lastScore = this.results.length ? this.results[this.results.length - 1][1] : null;
      st.results = [...this.results];
      st.report = [...this.reports];
      return st;
    }

    // done
    const avg = this.results.length
      ? this.results.reduce((s, [, v]) => s + v, 0) / this.results.length
      : 0;
    if (primary === null && now >= (this.deadline ?? now)) {
      this.resetForNewUser();
      return blank("idle", "카메라 앞에 서 주세요", 0, total);
    }
    const st = blank("done", `전체 완료! 평균 ${Math.round(avg)}점`, total, total);
    st.results = [...this.results];
    st.finalSummary = avg;
    st.report = [...this.reports];
    return st;
  }
}
