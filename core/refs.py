"""목표 자세 참조 스켈레톤 — JSON 저장 (config/refs.json). 웹앱과 동일 개념.

정규화 좌표(bbox 기준 0~1, 33x3: x,y,visibility)로 저장해 화면 크기와 무관하게 재사용.
관리자 화면에서 캡처 → 세션 중 가이드 썸네일로 표시.
"""

from __future__ import annotations

import json
import os

import numpy as np

from .pose_estimator import PersonPose

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "config", "refs.json")
REF_VIS = 0.3


def _load() -> dict[str, list[list[float]]]:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(m: dict) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)


def get_ref(pose: str) -> list[list[float]] | None:
    return _load().get(pose)


def set_ref(pose: str, normalized: list[list[float]]) -> None:
    m = _load()
    m[pose] = normalized
    _save(m)


def clear_ref(pose: str) -> None:
    m = _load()
    m.pop(pose, None)
    _save(m)


def has_ref(pose: str) -> bool:
    return get_ref(pose) is not None


def normalize_pose(pose: PersonPose) -> list[list[float]]:
    """라이브 포즈를 bbox 기준 0~1 로 정규화(저장용). visibility 유지."""
    x1, y1, x2, y2 = pose.bbox
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    out = []
    for k in pose.keypoints:
        out.append([float((k[0] - x1) / w), float((k[1] - y1) / h), float(k[2])])
    return out
