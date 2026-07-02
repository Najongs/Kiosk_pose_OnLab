"""난이도/테마 코스 로더. 웹앱과 config/courses.json 공유."""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "config", "courses.json")


_WEB_PATH = os.path.join(_ROOT, "web", "public", "courses.json")


def load_courses() -> list[dict]:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_courses(courses: list[dict]) -> None:
    """코스 목록 저장 + 웹앱(web/public)에도 동기화."""
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)
    try:
        if os.path.isdir(os.path.dirname(_WEB_PATH)):
            with open(_WEB_PATH, "w", encoding="utf-8") as f:
                json.dump(courses, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def new_course_id(courses: list[dict]) -> str:
    """겹치지 않는 코스 id 생성."""
    used = {c.get("id") for c in courses}
    n = 1
    while f"custom_{n}" in used:
        n += 1
    return f"custom_{n}"
