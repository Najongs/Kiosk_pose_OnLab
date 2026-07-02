/** 목표 자세 가이드: 참조 스켈레톤을 화면 우상단 썸네일 박스에 그린다.
 * 참조가 없으면(캡처 전) 박스는 생략하고 안내문(DOM)만 사용한다. */

import { REF_VIS } from "./refs";
import { SKELETON_EDGES } from "./keypoints";

export function drawGuideThumbnail(
  ctx: CanvasRenderingContext2D,
  refNorm: number[][] | null,
): void {
  if (!refNorm) return;
  const cw = ctx.canvas.width;
  const ch = ctx.canvas.height;
  // 우상단 박스 (화면의 22% 폭)
  const bw = cw * 0.22;
  const bh = bw * 1.25;
  const bx = cw - bw - cw * 0.02;
  const by = ch * 0.12;
  const pad = bw * 0.12;

  ctx.save();
  ctx.fillStyle = "rgba(10,12,20,0.72)";
  ctx.strokeStyle = "rgba(120,180,255,0.9)";
  ctx.lineWidth = Math.max(2, cw / 400);
  roundRect(ctx, bx, by, bw, bh, bw * 0.06);
  ctx.fill();
  ctx.stroke();

  // 라벨
  ctx.fillStyle = "#9fc2ff";
  ctx.font = `${Math.round(bh * 0.08)}px "Noto Sans KR", sans-serif`;
  ctx.textAlign = "center";
  ctx.fillText("목표 자세", bx + bw / 2, by + bh * 0.1);

  // 정규화(0~1) → 박스 내부 좌표
  const ix = bx + pad;
  const iy = by + bh * 0.14 + pad * 0.4;
  const iw = bw - pad * 2;
  const ih = bh - bh * 0.14 - pad * 1.4;
  const px = (nx: number) => ix + nx * iw;
  const py = (ny: number) => iy + ny * ih;

  ctx.strokeStyle = "#7fe7a0";
  ctx.lineWidth = Math.max(2, cw / 360);
  for (const [a, b] of SKELETON_EDGES) {
    if (refNorm[a][2] >= REF_VIS && refNorm[b][2] >= REF_VIS) {
      ctx.beginPath();
      ctx.moveTo(px(refNorm[a][0]), py(refNorm[a][1]));
      ctx.lineTo(px(refNorm[b][0]), py(refNorm[b][1]));
      ctx.stroke();
    }
  }
  ctx.fillStyle = "#ffd27f";
  const r = Math.max(2, cw / 500);
  for (const k of refNorm) {
    if (k[2] >= REF_VIS) {
      ctx.beginPath();
      ctx.arc(px(k[0]), py(k[1]), r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
