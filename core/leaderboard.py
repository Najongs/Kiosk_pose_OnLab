"""리더보드 — JSON 파일 저장 (data/leaderboard.json). 웹앱과 동일 데이터 모델."""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "leaderboard.json")


def _load() -> list[dict]:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(records: list[dict]) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=0)


def add_record(name: str, total: float, poses: list[tuple[str, float]], date: str) -> None:
    records = _load()
    records.append({
        "name": name,
        "total": total,
        "poses": [[n, s] for n, s in poses],
        "date": date,
    })
    _save(records)


def top_n(n: int = 10) -> list[dict]:
    return sorted(_load(), key=lambda r: r.get("total", 0), reverse=True)[:n]


def clear() -> None:
    _save([])
