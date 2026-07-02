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

function area(p: PersonPose): number {
  return Math.max(0, p.bbox[2] - p.bbox[0]) * Math.max(0, p.bbox[3] - p.bbox[1]);
}

function iou(a: number[], b: number[]): number {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  if (inter <= 0) return 0;
  const aa = Math.max(0, a[2] - a[0]) * Math.max(0, a[3] - a[1]);
  const ab = Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
  return inter / Math.max(1e-6, aa + ab - inter);
}

/** 같은 사람이 두 번 검출되는 경우 제거 — 많이 겹치면 큰 검출 하나만 남긴다. */
export function dedupePoses(poses: PersonPose[], iouThresh = 0.45): PersonPose[] {
  const out: PersonPose[] = [];
  for (const p of [...poses].sort((a, b) => area(b) - area(a))) {
    if (out.every((q) => iou(p.bbox, q.bbox) < iouThresh)) out.push(p);
  }
  return out;
}

/** 좌반=P1, 우반=P2. frameW 를 주면 화면 절반 기준 고정 배정 —
 * 혼자 오른쪽에 있으면 P2, 왼쪽 사람이 P2 가 되는 일이 없다. */
export function assignPlayers(
  poses: PersonPose[], frameW?: number,
): [PersonPose | null, PersonPose | null] {
  const ps = dedupePoses(poses);
  if (ps.length === 0) return [null, null];
  if (frameW) {
    const mid = frameW / 2;
    const left = ps.filter((p) => centerX(p) < mid);
    const right = ps.filter((p) => centerX(p) >= mid);
    const pick = (arr: PersonPose[]) =>
      arr.length ? arr.reduce((m, p) => (area(p) > area(m) ? p : m)) : null;
    return [pick(left), pick(right)];
  }
  const s = [...ps].sort((a, b) => centerX(a) - centerX(b));
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

  update(poses: PersonPose[], now: number, frameW?: number): VersusState {
    const total = this.defs.length;
    const [a, b] = assignPlayers(poses, frameW);
    const both = a !== null && b !== null;

    if (this.state === "idle") {
      if (both) {
        this.state = "countdown";
        this.deadline = now + this.countdownSeconds;
      }
      const oneSide = (a === null) !== (b === null);
      const msg = both ? "" : oneSide
        ? "한 명씩 화면 왼쪽/오른쪽에 서 주세요" : "두 명이 카메라 앞에 서 주세요";
      return this.snap("idle", msg, null, null,
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
