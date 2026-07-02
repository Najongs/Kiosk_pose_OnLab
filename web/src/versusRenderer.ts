/** 2인 대결 화면을 canvas 에 합성 (좌 P1 초록 / 우 P2 파랑, 분할 게이지 + 승자). */

import { PersonPose, SKELETON_EDGES } from "./keypoints";
import { VersusState } from "./versus";

const VIS = 0.3;

function skeleton(ctx: CanvasRenderingContext2D, pose: PersonPose | null,
                  sx: number, sy: number, color: string): void {
  if (!pose) return;
  const k = pose.keypoints;
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2, ctx.canvas.width / 320);
  for (const [i, j] of SKELETON_EDGES) {
    if (k[i][2] >= VIS && k[j][2] >= VIS) {
      ctx.beginPath();
      ctx.moveTo(k[i][0] * sx, k[i][1] * sy);
      ctx.lineTo(k[j][0] * sx, k[j][1] * sy);
      ctx.stroke();
    }
  }
}

function bar(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number,
             ratio: number, color: string): void {
  ctx.fillStyle = "rgba(70,70,70,0.6)";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w * Math.max(0, Math.min(1, ratio)), h);
  ctx.strokeStyle = "rgba(255,255,255,0.35)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
}

function text(ctx: CanvasRenderingContext2D, s: string, x: number, y: number,
              px: number, color: string, align: CanvasTextAlign = "left", weight = 700): void {
  ctx.font = `${weight} ${px}px "Noto Sans KR", sans-serif`;
  ctx.textAlign = align;
  ctx.lineWidth = Math.max(2, px / 8);
  ctx.strokeStyle = "rgba(0,0,0,0.7)";
  ctx.strokeText(s, x, y);
  ctx.fillStyle = color;
  ctx.fillText(s, x, y);
}

const P1_COLOR = "#2ee6a6";
const P2_COLOR = "#4aa8ff";

export function drawVersus(
  ctx: CanvasRenderingContext2D, video: HTMLVideoElement,
  p1pose: PersonPose | null, p2pose: PersonPose | null,
  state: VersusState, passAccuracy: number,
): void {
  const cw = ctx.canvas.width;
  const ch = ctx.canvas.height;
  const sx = cw / video.videoWidth;
  const sy = ch / video.videoHeight;
  ctx.clearRect(0, 0, cw, ch);
  ctx.drawImage(video, 0, 0, cw, ch);
  ctx.textBaseline = "alphabetic";

  // 중앙 분할선
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cw / 2, 0);
  ctx.lineTo(cw / 2, ch);
  ctx.stroke();

  skeleton(ctx, p1pose, sx, sy, P1_COLOR);
  skeleton(ctx, p2pose, sx, sy, P2_COLOR);

  // 상단 중앙: 자세명 + 라운드 타이머
  if (state.targetPose) {
    text(ctx, `자세 ${state.poseIndex + 1}/${state.poseTotal} · ${state.targetPose.display_name}`,
      cw / 2, ch * 0.07, Math.max(20, ch / 22), "#fff", "center", 800);
    if (state.roundRemaining !== null)
      text(ctx, `${Math.ceil(state.roundRemaining)}s`, cw / 2, ch * 0.13,
        Math.max(16, ch / 32), "#ffd27f", "center");
  }

  // 플레이어 패널
  const panel = (side: "l" | "r", label: string, color: string, p: typeof state.p1) => {
    const x = side === "l" ? cw * 0.03 : cw * 0.55;
    const w = cw * 0.42;
    text(ctx, `${label}  ${Math.round(p.total)}점`, x, ch * 0.20, Math.max(18, ch / 26), color, "left", 800);
    if (state.state === "playing") {
      const acc = p.accuracy;
      bar(ctx, x, ch * 0.23, w, ch * 0.035, acc === null ? 0 : acc / 100,
        acc !== null && acc >= passAccuracy ? color : "#c0c04a");
      text(ctx, acc === null ? "정확도 --" : `정확도 ${Math.round(acc)}%`, x, ch * 0.21,
        Math.max(14, ch / 36), "#fff");
      bar(ctx, x, ch * 0.29, w, ch * 0.025, p.holdProgress, "#f0b428");
      if (p.roundDone) text(ctx, "완료!", x + w, ch * 0.21, Math.max(16, ch / 30), color, "right", 800);
    }
  };
  panel("l", "P1", P1_COLOR, state.p1);
  panel("r", "P2", P2_COLOR, state.p2);

  if (state.state === "idle") {
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, ch * 0.42, cw, ch * 0.16);
    text(ctx, state.message, cw / 2, ch * 0.52, Math.max(26, ch / 18), "#fff", "center", 800);
  } else if (state.state === "countdown") {
    text(ctx, String(Math.ceil(state.countdownRemaining ?? 0)), cw / 2, ch * 0.6,
      Math.max(120, ch / 3), "#fff", "center", 900);
  } else if (state.state === "done") {
    ctx.fillStyle = "rgba(6,8,14,0.82)";
    ctx.fillRect(0, 0, cw, ch);
    const wc = state.winner === 1 ? P1_COLOR : state.winner === 2 ? P2_COLOR : "#fff";
    text(ctx, state.message, cw / 2, ch * 0.4, Math.max(48, ch / 9), wc, "center", 900);
    text(ctx, `P1  ${Math.round(state.p1.total)}점`, cw / 2, ch * 0.56, Math.max(28, ch / 18), P1_COLOR, "center", 800);
    text(ctx, `P2  ${Math.round(state.p2.total)}점`, cw / 2, ch * 0.66, Math.max(28, ch / 18), P2_COLOR, "center", 800);
  }
}
