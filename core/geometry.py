"""관절 각도 및 기하 유틸.

각도 기반 지표는 신체 크기·화면 내 위치에 불변이라 스코어링에 적합하다.
가능하면 world_landmarks(3D, 미터)를 쓰고, 없으면 2D 픽셀 좌표로 계산한다.
"""

from __future__ import annotations

import numpy as np


def angle_at(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """꼭짓점 b 에서 벡터 b->a 와 b->c 사이의 각도(도). 2D/3D 모두 지원."""
    ba = a - b
    bc = c - b
    nba = np.linalg.norm(ba)
    nbc = np.linalg.norm(bc)
    if nba < 1e-6 or nbc < 1e-6:
        return float("nan")
    cosang = float(np.dot(ba, bc) / (nba * nbc))
    cosang = max(-1.0, min(1.0, cosang))
    return float(np.degrees(np.arccos(cosang)))


def vector_angle_to_vertical(top: np.ndarray, bottom: np.ndarray) -> float:
    """top->bottom 선분이 수직축과 이루는 기울기 각도(도). 측면 굽히기용.

    2D 이미지 좌표(y 아래로 증가) 기준. 완전 수직이면 0도.
    """
    v = np.asarray(top[:2], dtype=np.float64) - np.asarray(bottom[:2], dtype=np.float64)
    n = np.linalg.norm(v)
    if n < 1e-6:
        return float("nan")
    # 수직 위 방향 벡터 (0, -1) 과의 각도
    vertical = np.array([0.0, -1.0])
    cosang = float(np.dot(v / n, vertical))
    cosang = max(-1.0, min(1.0, cosang))
    return float(np.degrees(np.arccos(cosang)))


def midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def select_coords(pose_keypoints: np.ndarray, world: np.ndarray | None, prefer_world: bool):
    """각도 계산에 쓸 좌표 배열을 고른다.

    prefer_world=True 이고 world 가 있으면 3D 좌표를, 아니면 2D(x,y) 픽셀 좌표를 반환.
    반환된 좌표와 visibility(항상 2D keypoints의 신뢰도) 를 함께 넘긴다.
    """
    vis = pose_keypoints[:, 2]
    if prefer_world and world is not None:
        return world[:, :3].astype(np.float64), vis
    return pose_keypoints[:, :2].astype(np.float64), vis


# 지표 이름 → 필요한 관절 인덱스 목록 (신뢰도 확인용)
def joint_angle(coords: np.ndarray, ai: int, bi: int, ci: int) -> float:
    return angle_at(coords[ai], coords[bi], coords[ci])
