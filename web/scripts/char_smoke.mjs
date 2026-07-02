// 3D 캐릭터 가이드 스모크: vite dev 서버 + headless WebGL 로 character.glb 를
// 로드·렌더해 스크린샷 저장. 실행: node scripts/char_smoke.mjs
import { spawn } from "node:child_process";
import { chromium } from "playwright";

const PORT = 5199;
const server = spawn("npx", ["vite", "--port", String(PORT), "--strictPort"], {
  cwd: new URL("..", import.meta.url).pathname,
  stdio: "pipe",
});
await new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error("vite 시작 시간초과")), 30000);
  const check = (d) => {
    process.stderr.write("[vite] " + String(d));
    if (String(d).includes("Local:")) { clearTimeout(t); res(); }
  };
  server.stdout.on("data", check);
  server.stderr.on("data", check);
});
console.log("vite up");

const browser = await chromium.launch({
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
  page.on("console", (m) => console.log("[page]", m.text()));
  page.on("pageerror", (e) => console.log("[pageerror]", String(e).slice(0, 300)));
  await page.goto(`http://localhost:${PORT}/`, { waitUntil: "domcontentloaded" });
  console.log("page loaded");
  const ok = await page.evaluate(async () => {
    console.log("step: import");
    const { CharacterGuide } = await import("/src/character3d.ts");
    console.log("step: imported");
    const canvas = document.getElementById("char3d");
    canvas.style.display = "block";
    canvas.style.width = "300px";
    canvas.style.height = "375px";
    canvas.style.position = "fixed";
    canvas.style.left = "20px";
    canvas.style.top = "20px";
    const g = new CharacterGuide(canvas);
    console.log("step: loading glb");
    const loaded = await g.load("/character.glb");
    console.log("step: loaded=" + loaded);
    if (!loaded) return false;
    g.setVisible(true);
    await new Promise((r) => setTimeout(r, 800));
    return g.ready;
  });
  console.log("character ready:", ok);
  const el = await page.$("#char3d");
  await el.screenshot({ path: "shots/char3d.png" });
  console.log("saved shots/char3d.png");
  process.exitCode = ok ? 0 : 1;
} finally {
  await browser.close();
  server.kill();
}
