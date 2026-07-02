/** 2인 실시간 대결 상태머신. 좌=P1, 우=P2 (bbox 중심 x 기준). 같은 자세를
 * 동시에 수행 → 라운드마다 각자 점수 → 총점 비교로 승자 판정. now 는 초 단위. */

import { HoldEvaluator } from "./hold";
import { PersonPose } from "./keypoints";
import { PoseDefinition } from "./poseDef";
import { PoseScorer } from "./scorer";

export type VState = "idle" | "countdown" | "playing" | "done";

export interface PlayerState {
  present: boolean;
  accuracy: number | null;
  holdProgress: number;
  roundDone: boolean;
  total: number; // 누적 총점
}

export interface VersusState {
  state: VState;
  message: string;
  poseIndex: number;
  poseTotal: number;
  targetPose: PoseDefinition | null;
  countdownRemaining: number | null;
  roundRemaining: number | null;
  p1: PlayerState;
  p2: PlayerState;
  winner: 0 | 1 | 2 | null; // 1=P1, 2=P2, 0=무승부, null=진행중
}

function centerX(p: PersonPose): number {
  return (p.bbox[0] + p.bbox[2]) / 2;
}

/** 좌=P1, 우=P2 로 배정. */
export function assignPlayers(poses: PersonPose[]): [PersonPose | null, PersonPose | null] {
  if (poses.length === 0) return [null, null];
  const s = [...poses].sort((a, b) => centerX(a) - centerX(b));
  if (s.length === 1) return [s[0], null];
  return [s[0], s[s.length - 1]];
}

export class VersusSession {
  private state: VState = "idle";
  private index = 0;
  private holds: [HoldEvaluator | null, HoldEvaluator | null] = [null, null];
  private done: [boolean, boolean] = [false, false];
  private peak: [number, number] = [0, 0];
  private totals: [number, number] = [0, 0];
  private deadline: number | null = null; // countdown 종료
  private roundDeadline: number | null = null;

  constructor(
    private defs: PoseDefinition[],
    private scorer: PoseScorer,
    private passAccuracy = 85,
    private countdownSeconds = 3,
    private roundTimeout = 15,
  ) {
    if (defs.length === 0) throw new Error("자세가 하나 이상 필요합니다");
  }

  private get cur(): PoseDefinition {
    return this.defs[this.index];
  }
  private newRound(): void {
    const hs = this.cur.hold_seconds ?? 3;
    this.holds = [
      new HoldEvaluator(this.passAccuracy, hs),
      new HoldEvaluator(this.passAccuracy, hs),
    ];
    this.done = [false, false];
    this.peak = [0, 0];
  }

  private playerScore(pose: PersonPose | null, i: 0 | 1, now: number): PlayerState {
    if (pose === null) {
      const st = this.holds[i] ? this.holds[i]!.update(0, false, now) : null;
      return { present: false, accuracy: null, holdProgress: st ? st.progress : 0,
        roundDone: this.done[i], total: this.totals[i] };
    }
    const r = this.scorer.score(pose, this.cur);
    const st = this.holds[i]!.update(r.accuracy, r.valid, now);
    this.peak[i] = Math.max(this.peak[i], r.accuracy);
    if (st.completed && !this.done[i]) {
      this.done[i] = true;
      this.totals[i] += st.avgAccuracy;
    }
    return {
      present: true, accuracy: r.accuracy, holdProgress: st.progress,
      roundDone: this.done[i], total: this.totals[i],
    };
  }

  update(poses: PersonPose[], now: number): VersusState {
    const total = this.defs.length;
    const [a, b] = assignPlayers(poses);
    const both = a !== null && b !== null;

    if (this.state === "idle") {
      if (both) {
        this.state = "countdown";
        this.deadline = now + this.countdownSeconds;
      }
      return this.snap("idle", both ? "" : "두 명이 카메라 앞에 서 주세요", null, null,
        { present: a !== null }, { present: b !== null });
    }

    if (this.state === "countdown") {
      if (!both) {
        this.state = "idle";
        return this.snap("idle", "두 명이 카메라 앞에 서 주세요", null, null, {}, {});
      }
      const rem = Math.max(0, (this.deadline ?? now) - now);
      if (rem <= 0) {
        this.state = "playing";
        this.index = 0;
        this.totals = [0, 0];
        this.newRound();
        this.roundDeadline = now + this.roundTimeout;
      } else {
        return this.snap("countdown", `'${this.cur.display_name}' 준비`, rem, null, {}, {});
      }
    }

    if (this.state === "playing") {
      const p1 = this.playerScore(a, 0, now);
      const p2 = this.playerScore(b, 1, now);
      const timeUp = now >= (this.roundDeadline ?? now);
      if ((this.done[0] && this.done[1]) || timeUp) {
        // 미완료자는 라운드 최고 정확도의 절반을 부분 점수로
        if (!this.done[0]) this.totals[0] += this.peak[0] * 0.5;
        if (!this.done[1]) this.totals[1] += this.peak[1] * 0.5;
        this.index += 1;
        if (this.index >= total) {
          this.state = "done";
          return this.doneState();
        }
        this.newRound();
        this.roundDeadline = now + this.roundTimeout;
        return this.buildPlaying(p1, p2, now);
      }
      return this.buildPlaying(p1, p2, now);
    }

    return this.doneState();
  }

  private doneState(): VersusState {
    const total = this.defs.length;
    const w: 0 | 1 | 2 =
      Math.abs(this.totals[0] - this.totals[1]) < 0.5 ? 0 : this.totals[0] > this.totals[1] ? 1 : 2;
    const msg = w === 0 ? "무승부!" : `Player ${w} 승리!`;
    return {
      state: "done", message: msg, poseIndex: total, poseTotal: total,
      targetPose: null, countdownRemaining: null, roundRemaining: null,
      p1: { present: false, accuracy: null, holdProgress: 0, roundDone: false, total: this.totals[0] },
      p2: { present: false, accuracy: null, holdProgress: 0, roundDone: false, total: this.totals[1] },
      winner: w,
    };
  }

  private buildPlaying(p1: PlayerState, p2: PlayerState, now: number): VersusState {
    const inDone = (this.state as VState) === "done";
    return {
      state: inDone ? "done" : "playing",
      message: `${this.cur ? this.cur.display_name : ""}`,
      poseIndex: Math.min(this.index, this.defs.length - 1),
      poseTotal: this.defs.length,
      targetPose: inDone ? null : this.cur,
      countdownRemaining: null,
      roundRemaining: Math.max(0, (this.roundDeadline ?? now) - now),
      p1, p2, winner: null,
    };
  }

  private snap(
    state: VState, message: string, countdownRemaining: number | null,
    roundRemaining: number | null, p1: Partial<PlayerState>, p2: Partial<PlayerState>,
  ): VersusState {
    const base = (): PlayerState => ({ present: false, accuracy: null, holdProgress: 0, roundDone: false, total: 0 });
    return {
      state, message, poseIndex: this.index, poseTotal: this.defs.length,
      targetPose: state === "countdown" ? this.cur : null,
      countdownRemaining, roundRemaining,
      p1: { ...base(), ...p1 }, p2: { ...base(), ...p2 }, winner: null,
    };
  }
}
