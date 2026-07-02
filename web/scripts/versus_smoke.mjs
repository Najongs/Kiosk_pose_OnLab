import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
const BASE = process.env.BASE || "http://localhost:4173";
mkdirSync("shots", { recursive: true });
const fake = resolve("scripts/fake2.y4m");
const browser = await chromium.launch({ args:[
  "--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream",
  `--use-file-for-fake-video-capture=${fake}`]});
const ctx = await browser.newContext({ viewport:{width:1280,height:720}, permissions:["camera"]});
const page = await ctx.newPage();
const errors=[];
page.on("console",m=>m.type()==="error"&&errors.push(m.text()));
page.on("pageerror",e=>errors.push(String(e)));
await page.addInitScript(()=>localStorage.setItem("onlab.config",JSON.stringify({
  poseSet:["tpose","overhead_reach"],passAccuracy:85,countdownSeconds:1,resultSeconds:1,holdSecondsOverride:2,sound:false,voice:false})));
await page.goto(BASE,{waitUntil:"networkidle"});
await page.click("#versusBtn",{force:true});
// 세션 진입 + 캔버스 리사이즈 대기
await page.waitForFunction(()=>!document.getElementById("session").classList.contains("hidden")
  && document.getElementById("canvas").width>400,{timeout:25000});
// playing 상태에서 두 명 검출될 때까지 폴링
let best=null;
for(let i=0;i<20;i++){
  await page.waitForTimeout(600);
  const s = await page.evaluate(()=>window.__vs);
  if(s){ best=s; if(s.state==="playing" && s.p1.present && s.p2.present) break; }
}
// 캔버스 픽셀을 직접 추출(스크린샷 컴포지터 우회)
const dataUrl = await page.evaluate(()=>document.getElementById("canvas").toDataURL("image/png"));
writeFileSync("shots/6_versus.png", Buffer.from(dataUrl.split(",")[1],"base64"));
console.log("versus state:", JSON.stringify({state:best?.state,p1:best?.p1,p2:best?.p2,pose:best?.targetPose?.display_name}));
console.log("errors:", errors.length?errors:"none");
await browser.close();
