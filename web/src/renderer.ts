/** 화면 렌더: <canvas> 에 영상+스켈레톤, DOM HUD 에 게이지·메시지·점수. */

import { PersonPose, SKELETON_EDGES } from "./keypoints";
import { SessionState } from "./session";

const VIS = 0.3;

export interface Hud {
  topbar: HTMLElement;
  poseIndex: HTMLElement;
  poseName: HTMLElement;
  accWrap: HTMLElement;
  accLabel: HTMLElement;
  accBar: HTMLElement;
  holdWrap: HTMLElement;
  holdBar: HTMLElement;
  center: HTMLElement;
  message: HTMLElement;
  summary: HTMLElement;
}

function accColor(acc: number, pass: number): string {
  if (acc >= pass) return "#2ecc40";
  if (acc >= pass * 0.6) return "#ffdc00";
  return "#ff4136";
}

export function drawFrame(
  ctx: CanvasRenderingContext2D,
  video: HTMLVideoElement,
  primary: PersonPose | null,
): void {
  const cw = ctx.canvas.width;
  const ch = ctx.canvas.height;
  ctx.clearRect(0, 0, cw, ch);
  ctx.drawImage(video, 0, 0, cw, ch);

  if (!primary) return;
  const kps = primary.keypoints;
  const sx = cw / video.videoWidth;
  const sy = ch / video.videoHeight;

  ctx.lineWidth = Math.max(2, cw / 320);
  ctx.strokeStyle = "#22eb22";
  for (const [a, b] of SKELETON_EDGES) {
    if (kps[a][2] >= VIS && kps[b][2] >= VIS) {
      ctx.beginPath();
      ctx.moveTo(kps[a][0] * sx, kps[a][1] * sy);
      ctx.lineTo(kps[b][0] * sx, kps[b][1] * sy);
      ctx.stroke();
    }
  }
  ctx.fillStyle = "#ffa000";
  const r = Math.max(3, cw / 240);
  for (const k of kps) {
    if (k[2] >= VIS) {
      ctx.beginPath();
      ctx.arc(k[0] * sx, k[1] * sy, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

export function updateHud(hud: Hud, state: SessionState, pass: number): void {
  // 상단바
  if (state.targetPose) {
    hud.topbar.style.display = "flex";
    hud.poseIndex.textContent = `자세 ${state.poseIndex + 1}/${state.poseTotal}`;
    hud.poseName.textContent = state.targetPose.display_name;
  } else {
    hud.topbar.style.display = "none";
  }

  const showAcc = state.state === "scoring";
  hud.accWrap.style.display = showAcc ? "block" : "none";
  hud.holdWrap.style.display = showAcc ? "block" : "none";
  if (showAcc) {
    const acc = state.accuracy;
    if (acc === null) {
      hud.accLabel.textContent = "정확도 --";
      hud.accBar.style.width = "0%";
    } else {
      hud.accLabel.textContent = `정확도 ${Math.round(acc)}%`;
      hud.accBar.style.width = `${Math.max(0, Math.min(100, acc))}%`;
      hud.accBar.style.background = accColor(acc, pass);
    }
    hud.holdBar.style.width = `${state.holdProgress * 100}%`;
  }

  // 중앙(카운트다운/결과) + 하단 메시지 + 완료 요약
  hud.center.style.display = "none";
  hud.summary.style.display = "none";
  hud.message.textContent = "";

  if (state.state === "idle") {
    hud.center.style.display = "block";
    hud.center.className = "center idle";
    hud.center.textContent = state.message;
  } else if (state.state === "countdown") {
    hud.center.style.display = "block";
    hud.center.className = "center countdown";
    hud.center.textContent = String(Math.ceil(state.countdownRemaining ?? 0));
    hud.message.textContent = state.message;
  } else if (state.state === "scoring") {
    hud.message.textContent = state.message;
  } else if (state.state === "result") {
    hud.center.style.display = "block";
    hud.center.className = "center result";
    hud.center.innerHTML = `<div class="done-label">완료!</div><div class="score">${Math.round(
      state.lastScore ?? 0,
    )}점</div>`;
  } else if (state.state === "done") {
    hud.summary.style.display = "flex";
    const rows = (state.report.length
      ? state.report.map((r) => {
          const angs = r.metrics.filter((m) => m.valid)
            .map((m) => `${Math.round(m.measured)}°`).slice(0, 3).join(" ");
          const asym = r.asymWarn
            ? `<span class="asym">좌우차 ${Math.round(r.maxAsymmetry ?? 0)}°</span>` : "";
          return `<div class="row report-row">
            <span class="r-name">${r.name}</span>
            <span class="r-ang">${angs}</span>
            <span class="r-grade">${r.grade}</span>
            <span class="r-score">${Math.round(r.score)}점</span>${asym}</div>`;
        })
      : state.results.map(([n, s]) =>
          `<div class="row"><span>${n}</span><span>${Math.round(s)}점</span></div>`)
    ).join("");
    hud.summary.innerHTML = `<h1>유연성 리포트</h1><div class="avg">평균 ${Math.round(
      state.finalSummary ?? 0,
    )}점</div><div class="report-list">${rows}</div>`;
  }
}
