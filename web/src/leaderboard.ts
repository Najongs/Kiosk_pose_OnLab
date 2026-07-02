/** 리더보드 — localStorage 기록/상위 N. (기기 로컬; 필요시 백엔드로 확장) */

export interface LeaderRecord {
  name: string;
  total: number; // 평균 점수
  poses: [string, number][]; // 자세별 점수
  date: string; // ISO
}

const KEY = "onlab.leaderboard";

export function loadAll(): LeaderRecord[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as LeaderRecord[];
  } catch {
    return [];
  }
}

export function addRecord(rec: LeaderRecord): void {
  const all = loadAll();
  all.push(rec);
  localStorage.setItem(KEY, JSON.stringify(all));
}

export function topN(n = 10): LeaderRecord[] {
  return loadAll()
    .slice()
    .sort((a, b) => b.total - a.total)
    .slice(0, n);
}

export function clearAll(): void {
  localStorage.removeItem(KEY);
}
