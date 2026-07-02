/** 유지시간 + 안정성 판정 — 파이썬 core/hold.py 와 동일. now 는 초 단위. */

export interface HoldStatus {
  holding: boolean;
  heldTime: number;
  progress: number; // 0~1
  success: boolean; // 이번 업데이트에서 완료 달성(1회성)
  completed: boolean;
  avgAccuracy: number;
}

export class HoldEvaluator {
  private heldTime = 0;
  private lastNow: number | null = null;
  private belowSince: number | null = null;
  private accSum = 0;
  private accDt = 0;
  private completed = false;

  constructor(
    private passAccuracy = 85,
    private holdSeconds = 3,
    private dropGrace = 0.4,
  ) {}

  reset(): void {
    this.heldTime = 0;
    this.lastNow = null;
    this.belowSince = null;
    this.accSum = 0;
    this.accDt = 0;
    this.completed = false;
  }

  update(accuracy: number, valid: boolean, now: number): HoldStatus {
    const dt = this.lastNow === null ? 0 : Math.max(0, now - this.lastNow);
    this.lastNow = now;
    const above = valid && accuracy >= this.passAccuracy;

    if (above) {
      this.belowSince = null;
      this.heldTime += dt;
      if (dt > 0) {
        this.accSum += accuracy * dt;
        this.accDt += dt;
      }
    } else {
      if (this.belowSince === null) this.belowSince = now;
      if (now - this.belowSince > this.dropGrace) {
        this.heldTime = 0;
        this.accSum = 0;
        this.accDt = 0;
        this.completed = false;
      }
    }

    const newlySuccess = !this.completed && this.heldTime >= this.holdSeconds;
    if (newlySuccess) this.completed = true;

    const avgAcc = this.accDt > 1e-6 ? this.accSum / this.accDt : 0;
    const progress = Math.min(1, this.heldTime / Math.max(this.holdSeconds, 1e-6));
    return {
      holding: above,
      heldTime: this.heldTime,
      progress,
      success: newlySuccess,
      completed: this.completed,
      avgAccuracy: avgAcc,
    };
  }
}
