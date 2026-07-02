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


# get_ref 는 세션 중 매 프레임 호출되므로 디스크를 매번 읽지 않고 메모리에
# 캐시한다. 파일 변경은 같은 프로세스의 set_ref/clear_ref 를 통해서만 일어난다
# (외부에서 refs.json 을 고치면 앱 재시작 필요).
_cache: dict[str, list[list[float]]] | None = None


def _load() -> dict[str, list[list[float]]]:
    global _cache
    if _cache is None:
        try:
            with open(_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
    return _cache


def _save(m: dict) -> None:
    global _cache
    _cache = m
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


# ---- 3D 참조 (world landmarks, 미터·엉덩이 원점) — 회전 캐릭터 가이드용 ----
_PATH3D = os.path.join(_ROOT, "config", "refs3d.json")
_cache3d: dict[str, list[list[float]]] | None = None


def _load3d() -> dict[str, list[list[float]]]:
    global _cache3d
    if _cache3d is None:
        try:
            with open(_PATH3D, encoding="utf-8") as f:
                _cache3d = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache3d = {}
    return _cache3d


def get_ref3d(pose: str) -> list[list[float]] | None:
    """자세의 3D 참조 (33 x [x, y, z, visibility]) 또는 None."""
    return _load3d().get(pose)


def set_ref3d(pose: str, joints: list[list[float]]) -> None:
    global _cache3d
    m = _load3d()
    m[pose] = joints
    _cache3d = m
    os.makedirs(os.path.dirname(_PATH3D), exist_ok=True)
    with open(_PATH3D, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)


def pose_to_ref3d(pose: PersonPose) -> list[list[float]] | None:
    """world_landmarks 를 [x,y,z,visibility] 리스트로 (없으면 None)."""
    if pose.world_landmarks is None:
        return None
    return [[float(wl[0]), float(wl[1]), float(wl[2]), float(kp[2])]
            for wl, kp in zip(pose.world_landmarks, pose.keypoints)]
