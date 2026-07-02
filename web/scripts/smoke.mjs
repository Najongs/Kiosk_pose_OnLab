// 브라우저 전체 파이프라인 스모크: 가짜 웹캠(y4m) → 포즈추정 → 세션 → 리더보드 기록.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.BASE || "http://localhost:4173";
const OUT = "shots";
mkdirSync(OUT, { recursive: true });
const fake = resolve("scripts/fake.y4m");

const browser = await chromium.launch({
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    `--use-file-for-fake-video-capture=${fake}`,
  ],
});
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  permissions: ["camera"],
});
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

// 스모크용 설정: 한 자세, 낮은 합격선, 짧은 타이밍
await page.addInitScript(() => {
  localStorage.setItem(
    "onlab.config",
    JSON.stringify({
      poseSet: ["forward_bend"],
      passAccuracy: 55,
      countdownSeconds: 1,
      resultSeconds: 1,
      holdSecondsOverride: 1,
      sound: false,
      voice: false,
    }),
  );
});

await page.goto(BASE, { waitUntil: "networkidle" });
await page.click("#startBtn");

// 채점 화면 도달 대기 (정확도 게이지가 보일 때)
await page
  .waitForFunction(() => {
    const w = document.getElementById("accWrap");
    return w && getComputedStyle(w).display !== "none";
  }, { timeout: 20000 })
  .catch(() => {});
await page.waitForTimeout(500);
await page.screenshot({ path: `${OUT}/4_session_scoring.png` });
const acc = await page.evaluate(() => document.getElementById("accLabel")?.textContent);
console.log("scoring accLabel:", acc);

// 완료(요약) 대기
const done = await page
  .waitForFunction(() => {
    const s = document.getElementById("summary");
    return s && getComputedStyle(s).display !== "none";
  }, { timeout: 25000 })
  .then(() => true)
  .catch(() => false);
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/5_session_done.png` });

const recs = await page.evaluate(() => JSON.parse(localStorage.getItem("onlab.leaderboard") || "[]"));
console.log("reachedDone:", done);
console.log("leaderboard records:", JSON.stringify(recs));
console.log("errors:", errors.length ? errors : "none");
await browser.close();
process.exit(done && recs.length > 0 ? 0 : 1);
