/** 앱 설정: 기본값 + localStorage 오버라이드(관리자 화면에서 수정). */

export interface AppConfig {
  poseSet: string[]; // 진행할 자세 이름 순서
  passAccuracy: number; // 합격 정확도(%)
  countdownSeconds: number;
  resultSeconds: number;
  holdSecondsOverride: number | null; // null 이면 자세별 hold_seconds 사용
  sound: boolean; // 효과음
  voice: boolean; // 음성 안내(TTS)
}

export const DEFAULT_CONFIG: AppConfig = {
  poseSet: ["forward_bend", "side_bend", "overhead_reach", "tpose"],
  passAccuracy: 85,
  countdownSeconds: 3,
  resultSeconds: 3,
  holdSecondsOverride: null,
  sound: true,
  voice: true,
};

const KEY = "onlab.config";

export function loadConfig(): AppConfig {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_CONFIG };
    return { ...DEFAULT_CONFIG, ...(JSON.parse(raw) as Partial<AppConfig>) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function saveConfig(cfg: AppConfig): void {
  localStorage.setItem(KEY, JSON.stringify(cfg));
}

export function resetConfig(): void {
  localStorage.removeItem(KEY);
}
