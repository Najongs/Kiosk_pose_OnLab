"""자세 정의 모델 + 로더.

자세는 '지표(metric) 목록'으로 정의한다. 각 지표는 관절 각도 또는 몸통 기울기
같은 측정 가능한 값과, 목표값·허용오차·가중치를 가진다.

두 가지 정의 방식(계획서 4번):
  (a) 개발자 각도 기준: config/poses/<name>.json 에 각도 스펙을 직접 기술.
  (b) 관리자 캡처: 이상적 자세를 캡처해 각도를 자동 산출 → 같은 JSON 스키마로 저장.
      (도출 로직은 admin 화면에서, 여기선 동일 스키마를 읽기만 하면 됨.)

특수 포인트 이름:
  "<part>_mid"  → 좌우 관절의 중점 (예: shoulder_mid, hip_mid)
  그 외         → pose_estimator.KEYPOINT_NAMES 의 이름 (예: left_hip)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .pose_estimator import KEYPOINT_NAMES

POSES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "poses"
)


@dataclass
class Metric:
    id: str
    type: str  # "angle" | "lean"
    target: float
    tolerance: float
    weight: float = 1.0
    # angle: joints=[a,b,c] (base 또는 정확한 이름), side="both"|"left"|"right"
    joints: list[str] = field(default_factory=list)
    side: str = "both"
    # side="both" 일 때 좌우 값을 합치는 방식: mean|min|max
    # (예: 한발 서기의 접힌 무릎은 min, 편 다리는 max 로 잡는다)
    aggregate: str = "mean"
    # lean: top/bottom 포인트 이름
    top: str | None = None
    bottom: str | None = None


@dataclass
class PoseDefinition:
    name: str
    display_name: str
    description: str = ""
    prefer_world: bool = True
    hold_seconds: float = 3.0
    metrics: list[Metric] = field(default_factory=list)


def _resolve_point_indices(name: str, side: str | None = None) -> list[int] | str:
    """포인트 이름을 키포인트 인덱스(들)로 변환.

    반환이 list[int] 이고 len>1 이면 그 인덱스들의 중점을 쓰라는 의미(_mid).
    """
    if name.endswith("_mid"):
        base = name[:-4]
        return [KEYPOINT_NAMES[f"left_{base}"], KEYPOINT_NAMES[f"right_{base}"]]
    # side 접두사 적용 (angle 관절의 base 이름 처리)
    if side in ("left", "right") and f"{side}_{name}" in KEYPOINT_NAMES:
        return [KEYPOINT_NAMES[f"{side}_{name}"]]
    if name in KEYPOINT_NAMES:
        return [KEYPOINT_NAMES[name]]
    raise KeyError(f"알 수 없는 포인트 이름: {name} (side={side})")


def resolve_point(name: str, side: str | None = None) -> list[int]:
    r = _resolve_point_indices(name, side)
    return r  # list[int]; len==1 단일 관절, len>1 중점


def load_pose(name: str) -> PoseDefinition:
    path = name if os.path.isfile(name) else os.path.join(POSES_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    metrics = [Metric(**m) for m in data.get("metrics", [])]
    return PoseDefinition(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        description=data.get("description", ""),
        prefer_world=data.get("prefer_world", True),
        hold_seconds=data.get("hold_seconds", 3.0),
        metrics=metrics,
    )


def list_poses() -> list[str]:
    if not os.path.isdir(POSES_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0] for f in os.listdir(POSES_DIR) if f.endswith(".json")
    )
