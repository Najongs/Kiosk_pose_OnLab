// 헤드리스 Chromium 으로 홈/리더보드/관리자 화면을 스크린샷 (카메라 불필요).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE || "http://localhost:4173";
const OUT = "shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/1_home_empty.png` });

// 리더보드 시드 후 재로드
await page.evaluate(() => {
  const recs = [
    { name: "지민", total: 92, poses: [], date: "" },
    { name: "현우", total: 88, poses: [], date: "" },
    { name: "서연", total: 81, poses: [], date: "" },
    { name: "익명", total: 74, poses: [], date: "" },
  ];
  localStorage.setItem("onlab.leaderboard", JSON.stringify(recs));
});
await page.reload({ waitUntil: "networkidle" });
await page.fill("#nameInput", "테스터");
await page.waitForTimeout(200);
await page.screenshot({ path: `${OUT}/2_home_leaderboard.png` });

// 관리자
await page.click("#adminOpen");
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/3_admin.png`, fullPage: true });

console.log("errors:", errors.length ? errors : "none");
await browser.close();
