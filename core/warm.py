"""앱 수명 동안 재사용하는 무거운 리소스(포즈 모델) 캐시.

MediaPipe 모델 로드는 수 초가 걸리므로 세션을 시작할 때마다 새로 만들지 않고
프로세스당 한 번만 만들어 재사용한다(num_poses 별 1개). 세션 뷰의 워커
스레드들이 시점을 달리해 접근하므로 생성은 락으로 직렬화한다.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_estimators: dict[int, object] = {}


def get_estimator(num_poses: int = 1, **kwargs):
    """공유 MediaPipeEstimator 를 반환(없으면 생성). close() 하지 말 것."""
    with _lock:
        est = _estimators.get(num_poses)
        if est is None:
            from .mediapipe_estimator import MediaPipeEstimator
            est = MediaPipeEstimator(num_poses=num_poses, **kwargs)
            _estimators[num_poses] = est
        return est


def close_all() -> None:
    """앱 종료 시 정리."""
    with _lock:
        for est in _estimators.values():
            try:
                est.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        _estimators.clear()
