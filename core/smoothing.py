"""키포인트 시간적 스무딩 — One Euro Filter.

MediaPipe 랜드마크는 프레임마다 미세하게 떨린다(특히 lite/full 모델, 저조도).
One Euro Filter(Casiez et al., CHI 2012)는 느린 움직임에서는 강하게 눌러
떨림을 없애고, 빠른 움직임에서는 필터를 풀어 지연을 최소화하는 적응형
저역통과 필터다 — 포즈 인터랙션의 사실상 표준.

시간(now)은 초 단위 float 외부 주입 (게임 로직과 같은 관례 — 테스트 용이).
"""

from __future__ import annotations

import math

import numpy as np

from .pose_estimator import PersonPose


class OneEuroFilter:
    """스칼라 배열용 One Euro Filter (키포인트 (N,2)/(N,3) 벡터화)."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02,
                 d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)  # 낮을수록 정지 시 더 강하게 스무딩
        self.beta = float(beta)              # 클수록 빠른 움직임에 빨리 반응
        self.d_cutoff = float(d_cutoff)
        self._prev_t: float | None = None
        self._prev_x: np.ndarray | None = None
        self._prev_dx: np.ndarray | None = None

    @staticmethod
    def _alpha(cutoff, dt: float):
        tau = 1.0 / (2.0 * math.pi) / np.maximum(cutoff, 1e-6)
        return 1.0 / (1.0 + tau / max(dt, 1e-6))

    def reset(self) -> None:
        self._prev_t = None
        self._prev_x = None
        self._prev_dx = None

    def __call__(self, x: np.ndarray, now: float) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if self._prev_x is None or self._prev_t is None or now <= self._prev_t:
            self._prev_t = now
            self._prev_x = x.copy()
            self._prev_dx = np.zeros_like(x)
            return x.copy()
        dt = now - self._prev_t
        dx = (x - self._prev_x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self._prev_dx
        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self._prev_x
        self._prev_t = now
        self._prev_x = x_hat
        self._prev_dx = dx_hat
        return x_hat.copy()


class PoseSmoother:
    """PersonPose 하나(동일 인물로 추적된)의 픽셀/월드 좌표를 스무딩.

    사람이 사라지거나 추적 id 가 바뀌면 reset() 할 것 — 다른 사람의 좌표에
    이어붙으면 순간이동 잔상이 생긴다. visibility 는 스무딩하지 않는다.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.015):
        self._px = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        # 월드 좌표는 미터 단위(값이 작음) — 속도 반응 계수를 크게
        self._world = OneEuroFilter(min_cutoff=min_cutoff, beta=beta * 400)

    def reset(self) -> None:
        self._px.reset()
        self._world.reset()

    def apply(self, pose: PersonPose, now: float) -> PersonPose:
        kps = pose.keypoints.copy()
        kps[:, :2] = self._px(pose.keypoints[:, :2], now).astype(np.float32)
        world = pose.world_landmarks
        if world is not None:
            world = self._world(world, now).astype(np.float32)
        x1 = float(kps[:, 0].min())
        y1 = float(kps[:, 1].min())
        x2 = float(kps[:, 0].max())
        y2 = float(kps[:, 1].max())
        return PersonPose(keypoints=kps, bbox=(x1, y1, x2, y2),
                          world_landmarks=world, track_id=pose.track_id,
                          extra=pose.extra)
