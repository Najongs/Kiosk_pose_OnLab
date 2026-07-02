/** 관리자 화면: 설정 편집 + 자세 세트 + 목표 자세 참조 캡처 + 초기화. */

import { AppConfig, loadConfig, resetConfig, saveConfig } from "./config";
import { listPoses, loadPose, PoseDefinition } from "./poseDef";
import { clearAll as clearLeaderboard } from "./leaderboard";
import { normalizePose, setRef, hasRef, clearRef } from "./refs";
import { Camera } from "./pipeline";
import { drawFrame } from "./renderer";
import { pickPrimary } from "./poseEstimator";

const $ = (id: string) => document.getElementById(id)!;

export function initAdmin(): void {
  const cfg = loadConfig();
  const passRange = $("passRange") as HTMLInputElement;
  const passVal = $("passVal");
  const countdownInput = $("countdownInput") as HTMLInputElement;
  const holdInput = $("holdInput") as HTMLInputElement;
  const soundChk = $("soundChk") as HTMLInputElement;
  const voiceChk = $("voiceChk") as HTMLInputElement;
  const status = $("adminStatus");

  // 폼 채우기
  passRange.value = String(cfg.passAccuracy);
  passVal.textContent = String(cfg.passAccuracy);
  countdownInput.value = String(cfg.countdownSeconds);
  holdInput.value = cfg.holdSecondsOverride === null ? "" : String(cfg.holdSecondsOverride);
  soundChk.checked = cfg.sound;
  voiceChk.checked = cfg.voice;

  const save = (patch: Partial<AppConfig>) => {
    const next = { ...loadConfig(), ...patch };
    saveConfig(next);
    flash("저장됨");
  };
  const flash = (msg: string) => {
    status.textContent = msg;
    setTimeout(() => (status.textContent = ""), 1500);
  };

  passRange.oninput = () => (passVal.textContent = passRange.value);
  passRange.onchange = () => save({ passAccuracy: Number(passRange.value) });
  countdownInput.onchange = () => save({ countdownSeconds: Number(countdownInput.value) });
  holdInput.onchange = () =>
    save({ holdSecondsOverride: holdInput.value === "" ? null : Number(holdInput.value) });
  soundChk.onchange = () => save({ sound: soundChk.checked });
  voiceChk.onchange = () => save({ voice: voiceChk.checked });

  $("clearLb").onclick = () => {
    if (confirm("리더보드를 초기화할까요?")) {
      clearLeaderboard();
      flash("리더보드 초기화됨");
    }
  };
  $("resetCfg").onclick = () => {
    if (confirm("모든 설정을 기본값으로 되돌릴까요?")) {
      resetConfig();
      flash("설정 초기화됨 — 새로고침하세요");
    }
  };

  void buildPoseUI(cfg);
  setupCapture();
}

async function buildPoseUI(cfg: AppConfig): Promise<void> {
  const names = await listPoses();
  const defs = await Promise.all(names.map(loadPose));
  const byName = new Map(defs.map((d) => [d.name, d]));

  // 자세 세트 체크박스 (체크된 것 = 진행, 순서는 config.poseSet 유지 + 나머지)
  const listEl = $("poseSetList");
  listEl.innerHTML = "";
  const ordered = [...cfg.poseSet, ...names.filter((n) => !cfg.poseSet.includes(n))];
  for (const name of ordered) {
    const d = byName.get(name);
    if (!d) continue;
    const row = document.createElement("label");
    row.className = "pose-row";
    const checked = cfg.poseSet.includes(name);
    row.innerHTML = `<input type="checkbox" ${checked ? "checked" : ""} value="${name}" />
      <span>${d.display_name}</span>
      <em class="${hasRef(name) ? "ref-on" : "ref-off"}">${hasRef(name) ? "가이드 있음" : "가이드 없음"}</em>`;
    listEl.appendChild(row);
  }
  listEl.onchange = () => {
    const checks = Array.from(listEl.querySelectorAll<HTMLInputElement>("input:checked"));
    const set = checks.map((c) => c.value);
    if (set.length === 0) return;
    saveConfig({ ...loadConfig(), poseSet: set });
  };

  // 캡처 대상 셀렉트
  const sel = $("captureSel") as HTMLSelectElement;
  sel.innerHTML = defs.map((d) => `<option value="${d.name}">${d.display_name}</option>`).join("");
}

function setupCapture(): void {
  const startBtn = $("captureStart") as HTMLButtonElement;
  const shotBtn = $("captureShot") as HTMLButtonElement;
  const stopBtn = $("captureStop") as HTMLButtonElement;
  const sel = $("captureSel") as HTMLSelectElement;
  const stage = $("captureStage");
  const video = $("capVideo") as HTMLVideoElement;
  const canvas = $("capCanvas") as HTMLCanvasElement;
  const ctx = canvas.getContext("2d")!;
  const status = $("adminStatus");

  const cam = new Camera(video);
  let running = false;
  let lastPrimary: ReturnType<typeof pickPrimary> = null;
  let raf = 0;

  const loop = () => {
    if (!running) return;
    if (cam.ready()) {
      if (canvas.width !== cam.width) {
        canvas.width = cam.width;
        canvas.height = cam.height;
      }
      const poses = cam.estimate(performance.now());
      lastPrimary = pickPrimary(poses);
      drawFrame(ctx, video, lastPrimary);
      shotBtn.disabled = lastPrimary === null;
    }
    raf = requestAnimationFrame(loop);
  };

  startBtn.onclick = async () => {
    try {
      status.textContent = "카메라 시작 중…";
      await cam.ensure(1);
      stage.classList.remove("hidden");
      running = true;
      startBtn.disabled = true;
      stopBtn.disabled = false;
      status.textContent = "";
      raf = requestAnimationFrame(loop);
    } catch (e: any) {
      status.textContent = `카메라 오류: ${e?.message ?? e}`;
    }
  };

  shotBtn.onclick = () => {
    if (!lastPrimary) return;
    const pose = sel.value;
    setRef(pose, normalizePose(lastPrimary));
    status.textContent = `'${sel.selectedOptions[0].text}' 목표 자세 저장됨`;
    const row = document.querySelector<HTMLElement>(`#poseSetList input[value="${pose}"]`)
      ?.parentElement?.querySelector("em");
    if (row) {
      row.textContent = "가이드 있음";
      row.className = "ref-on";
    }
  };

  stopBtn.onclick = () => {
    running = false;
    cancelAnimationFrame(raf);
    cam.stopStream();
    stage.classList.add("hidden");
    startBtn.disabled = false;
    stopBtn.disabled = true;
    shotBtn.disabled = true;
  };

  // 참조 삭제(길게 눌러) — 셀렉트 우클릭
  sel.oncontextmenu = (e) => {
    e.preventDefault();
    if (confirm(`'${sel.selectedOptions[0].text}' 가이드를 삭제할까요?`)) {
      clearRef(sel.value);
      status.textContent = "가이드 삭제됨";
    }
  };
}

export type { PoseDefinition };
