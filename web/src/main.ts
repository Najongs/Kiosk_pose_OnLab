/** 앱 컨트롤러: 홈 ↔ 세션 ↔ 관리자. 세션 루프에 음성/사운드·가이드·리더보드 연결. */

import "./styles.css";
import { loadConfig } from "./config";
import { addRecord, topN } from "./leaderboard";
import { loadPose } from "./poseDef";
import { PoseScorer } from "./scorer";
import { Session, SessionState } from "./session";
import { Camera } from "./pipeline";
import { drawFrame, updateHud, Hud } from "./renderer";
import { pickPrimary } from "./poseEstimator";
import { CharacterGuide } from "./character3d";
import { drawGuideThumbnail } from "./guide";
import { getRef } from "./refs";
import * as audio from "./audio";
import { initAdmin } from "./admin";
import { loadCourses } from "./courses";
import { VersusSession } from "./versus";
import { assignPlayers } from "./versus";
import { drawVersus } from "./versusRenderer";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const screens = {
  home: $("home"),
  session: $("session"),
  admin: $("admin"),
};
function show(name: keyof typeof screens): void {
  for (const [k, el] of Object.entries(screens)) el.classList.toggle("hidden", k !== name);
}

// ---------- 홈 / 리더보드 ----------
function renderLeaderboard(): void {
  const list = $("lbList");
  const rows = topN(10);
  if (rows.length === 0) {
    list.innerHTML = `<li class="empty">아직 기록이 없어요. 첫 도전자가 되어보세요!</li>`;
    return;
  }
  const medals = ["🥇", "🥈", "🥉"];
  list.innerHTML = rows
    .map(
      (r, i) =>
        `<li><span class="rank">${medals[i] ?? i + 1}</span>
         <span class="who">${escapeHtml(r.name || "익명")}</span>
         <span class="pts">${Math.round(r.total)}점</span></li>`,
    )
    .join("");
}
function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

// ---------- 세션 ----------
let camera: Camera | null = null;
let running = false;
let raf = 0;

// 3D 캐릭터 가이드 (public/character.glb 있으면 활성 — 없으면 2D 썸네일)
const charGuide = new CharacterGuide($<HTMLCanvasElement>("char3d"));
void charGuide.load();

async function startSession(poses?: string[]): Promise<void> {
  const status = $("homeStatus");
  const cfg = loadConfig();
  const poseSet = poses && poses.length ? poses : cfg.poseSet;
  audio.unlockAudio();

  try {
    status.textContent = "모델·카메라 준비 중…";
    const video = $<HTMLVideoElement>("video");
    camera ??= new Camera(video);
    await camera.ensure(1);

    const defs = await Promise.all(poseSet.map(loadPose));
    if (cfg.holdSecondsOverride !== null)
      for (const d of defs) d.hold_seconds = cfg.holdSecondsOverride;
    const session = new Session(
      defs,
      new PoseScorer(),
      cfg.passAccuracy,
      cfg.countdownSeconds,
      cfg.resultSeconds,
    );

    const canvas = $<HTMLCanvasElement>("canvas");
    const ctx = canvas.getContext("2d")!;
    const hud: Hud = {
      topbar: $("topbar"), poseIndex: $("poseIndex"), poseName: $("poseName"),
      accWrap: $("accWrap"), accLabel: $("accLabel"), accBar: $("accBar"),
      holdWrap: $("holdWrap"), holdBar: $("holdBar"),
      center: $("center"), message: $("message"), summary: $("summary"),
    };
    const homeBtn = $("homeBtn");
    homeBtn.classList.add("hidden");
    status.textContent = "";
    show("session");

    const name = ($<HTMLInputElement>("nameInput").value || "").trim();
    const cue = makeCue(cfg.sound, cfg.voice);
    let savedDone = false;
    running = true;

    const loop = () => {
      if (!running) return;
      if (camera!.ready()) {
        if (canvas.width !== camera!.width) {
          canvas.width = camera!.width;
          canvas.height = camera!.height;
        }
        const primary = pickPrimary(camera!.estimate(performance.now()));
        const state = session.update(primary, performance.now() / 1000);
        drawFrame(ctx, camera!.el, primary);
        const guiding = !!state.targetPose &&
          (state.state === "countdown" || state.state === "scoring");
        charGuide.setVisible(guiding);  // 3D 캐릭터 있으면 오버레이로
        if (guiding && !charGuide.ready)
          drawGuideThumbnail(ctx, getRef(state.targetPose!.name));
        updateHud(hud, state, cfg.passAccuracy);
        cue(state);

        if (state.state === "done" && !savedDone) {
          savedDone = true;
          addRecord({
            name,
            total: state.finalSummary ?? 0,
            poses: state.results,
            date: new Date().toISOString(),
          });
          homeBtn.classList.remove("hidden");
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
  } catch (e: any) {
    status.textContent = `오류: ${e?.message ?? e}`;
    console.error(e);
  }
}

function endSession(): void {
  running = false;
  charGuide.setVisible(false);
  cancelAnimationFrame(raf);
  audio.cancelSpeak();
  camera?.stopStream();
  renderLeaderboard();
  show("home");
  $("nameInput").focus?.();
}

// ---------- 2인 대결 ----------
async function startVersus(): Promise<void> {
  const status = $("homeStatus");
  const cfg = loadConfig();
  audio.unlockAudio();
  try {
    status.textContent = "모델·카메라 준비 중… (2인)";
    const video = $<HTMLVideoElement>("video");
    camera ??= new Camera(video);
    await camera.ensure(2);

    const defs = await Promise.all(cfg.poseSet.map(loadPose));
    const vs = new VersusSession(defs, new PoseScorer(), cfg.passAccuracy, cfg.countdownSeconds);

    const canvas = $<HTMLCanvasElement>("canvas");
    const ctx = canvas.getContext("2d")!;
    // 솔로 HUD 숨김 (대결은 캔버스에 직접 그림)
    for (const id of ["topbar", "accWrap", "holdWrap", "center", "message", "summary"])
      $(id).style.display = "none";
    const homeBtn = $("homeBtn");
    homeBtn.classList.remove("hidden");
    status.textContent = "";
    show("session");

    const cue = makeVersusCue(cfg.sound, cfg.voice);
    running = true;
    const loop = () => {
      if (!running) return;
      if (camera!.ready()) {
        if (canvas.width !== camera!.width) {
          canvas.width = camera!.width;
          canvas.height = camera!.height;
        }
        const poses = camera!.estimate(performance.now());
        const [a, b] = assignPlayers(poses, canvas.width); // 좌반=P1, 우반=P2
        const state = vs.update(poses, performance.now() / 1000, canvas.width);
        drawVersus(ctx, camera!.el, a, b, state, cfg.passAccuracy);
        cue(state);
        (window as unknown as { __vs?: unknown }).__vs = state;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
  } catch (e: any) {
    status.textContent = `오류: ${e?.message ?? e}`;
    console.error(e);
  }
}

function makeVersusCue(sound: boolean, voice: boolean) {
  let prev = "";
  return (s: { state: string; winner: number | null; message: string }) => {
    if (s.state !== prev) {
      if (s.state === "playing" && sound) audio.go();
      if (s.state === "done") {
        if (sound) audio.fanfare();
        if (voice) audio.speak(s.message);
      }
      prev = s.state;
    }
  };
}

// ---------- 음성/사운드 큐 (상태 전이 시 1회성) ----------
function makeCue(sound: boolean, voice: boolean) {
  let prevState = "";
  let prevIndex = -1;
  let prevCount = -1;
  return (s: SessionState) => {
    const enteredState = s.state !== prevState || s.poseIndex !== prevIndex;
    if (s.state === "countdown") {
      if (enteredState && voice && s.targetPose) audio.speak(`${s.targetPose.display_name} 준비`);
      const c = Math.ceil(s.countdownRemaining ?? 0);
      if (c !== prevCount && c > 0 && sound) audio.tick();
      prevCount = c;
    } else if (s.state === "scoring") {
      if (enteredState && sound) audio.go();
      prevCount = -1;
    } else if (s.state === "result") {
      if (enteredState) {
        if (sound) audio.success();
        if (voice) audio.speak(`완료! ${Math.round(s.lastScore ?? 0)}점`);
      }
    } else if (s.state === "done") {
      if (enteredState) {
        if (sound) audio.fanfare();
        if (voice) audio.speak(`전체 완료! 평균 ${Math.round(s.finalSummary ?? 0)}점`);
      }
    }
    prevState = s.state;
    prevIndex = s.poseIndex;
  };
}

// ---------- 코스 ----------
async function renderCourses(): Promise<void> {
  const wrap = $("courses");
  const courses = await loadCourses();
  wrap.innerHTML = "";
  for (const c of courses) {
    const card = document.createElement("button");
    card.className = "course-card";
    card.innerHTML = `<span class="diff diff-${diffClass(c.difficulty)}">${c.difficulty}</span>
      <span class="c-name">${escapeHtml(c.name)}</span>
      <span class="c-desc">${escapeHtml(c.desc)}</span>
      <span class="c-count">${c.poses.length}개 자세</span>`;
    card.addEventListener("click", () => startSession(c.poses));
    wrap.appendChild(card);
  }
}
function diffClass(d: string): string {
  return d === "초급" ? "easy" : d === "중급" ? "mid" : "hard";
}

// ---------- 부팅 ----------
function boot(): void {
  renderLeaderboard();
  void renderCourses();
  $("startBtn").addEventListener("click", () => startSession());
  $("versusBtn").addEventListener("click", () => startVersus());
  $("homeBtn").addEventListener("click", endSession);
  $("quitBtn").addEventListener("click", endSession);

  let adminReady = false;
  $("adminOpen").addEventListener("click", () => {
    if (!adminReady) {
      initAdmin();
      adminReady = true;
    }
    show("admin");
  });
  $("adminClose").addEventListener("click", () => {
    (document.getElementById("captureStop") as HTMLButtonElement)?.click();
    renderLeaderboard();
    show("home");
  });
}

boot();
