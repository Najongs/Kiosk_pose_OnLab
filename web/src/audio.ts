/** 사운드 + 음성 안내. WebAudio 비프/차임 + speechSynthesis 한국어 TTS. */

let ctx: AudioContext | null = null;
function ac(): AudioContext {
  if (!ctx) ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
  return ctx;
}

export function unlockAudio(): void {
  // 사용자 제스처 시점에 호출해 오디오 컨텍스트 활성화
  try {
    void ac().resume();
  } catch {
    /* noop */
  }
}

function tone(freq: number, durMs: number, type: OscillatorType = "sine", gain = 0.18): void {
  try {
    const a = ac();
    const osc = a.createOscillator();
    const g = a.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.value = gain;
    osc.connect(g);
    g.connect(a.destination);
    const now = a.currentTime;
    osc.start(now);
    g.gain.setValueAtTime(gain, now);
    g.gain.exponentialRampToValueAtTime(0.0001, now + durMs / 1000);
    osc.stop(now + durMs / 1000);
  } catch {
    /* 오디오 불가 환경 무시 */
  }
}

export function tick(): void {
  tone(660, 110, "square", 0.12);
}
export function go(): void {
  tone(990, 220, "sawtooth", 0.16);
}
export function success(): void {
  tone(880, 120);
  setTimeout(() => tone(1175, 130), 120);
  setTimeout(() => tone(1568, 200), 250);
}
export function fanfare(): void {
  [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => tone(f, 200), i * 160));
}

let koVoice: SpeechSynthesisVoice | null = null;
function pickVoice(): SpeechSynthesisVoice | null {
  if (koVoice) return koVoice;
  const voices = window.speechSynthesis?.getVoices?.() ?? [];
  koVoice = voices.find((v) => v.lang?.toLowerCase().startsWith("ko")) ?? null;
  return koVoice;
}

export function speak(text: string): void {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    const v = pickVoice();
    if (v) u.voice = v;
    u.rate = 1.05;
    synth.speak(u);
  } catch {
    /* TTS 불가 무시 */
  }
}

export function cancelSpeak(): void {
  try {
    window.speechSynthesis?.cancel();
  } catch {
    /* noop */
  }
}
