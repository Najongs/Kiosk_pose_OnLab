/** 난이도/테마 코스 로더. 파이썬과 config/courses.json 공유. */

export interface Course {
  id: string;
  name: string;
  difficulty: string;
  desc: string;
  poses: string[];
}

export async function loadCourses(): Promise<Course[]> {
  try {
    const res = await fetch("courses.json");
    if (!res.ok) return [];
    return (await res.json()) as Course[];
  } catch {
    return [];
  }
}
