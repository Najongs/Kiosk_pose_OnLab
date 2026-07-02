import { chromium } from "playwright";
import { resolve } from "node:path";
const fake = resolve("scripts/fake2.y4m");
const browser = await chromium.launch({ args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream",`--use-file-for-fake-video-capture=${fake}`]});
const ctx = await browser.newContext({ viewport:{width:1280,height:720}, permissions:["camera"]});
const page = await ctx.newPage();
const errors=[];
page.on("console",m=>m.type()==="error"&&errors.push(m.text().slice(0,160)));
page.on("pageerror",e=>errors.push("PE:"+String(e).slice(0,160)));
await page.addInitScript(()=>localStorage.setItem("onlab.config",JSON.stringify({poseSet:["tpose"],passAccuracy:85,countdownSeconds:1,resultSeconds:1,holdSecondsOverride:2,sound:false,voice:false})));
await page.goto("http://localhost:4193",{waitUntil:"networkidle"});
await page.locator("#versusBtn").dispatchEvent("click");
for (let i=0;i<6;i++){
  await page.waitForTimeout(2000);
  const st = await page.evaluate(()=>({sess:!document.getElementById("session").classList.contains("hidden"),cw:document.getElementById("canvas").width,status:document.getElementById("homeStatus").textContent})).catch(e=>({err:String(e)}));
  console.log(i, JSON.stringify(st), "errs", errors.length);
}
console.log("ERRORS", errors.slice(0,6));
await browser.close();
