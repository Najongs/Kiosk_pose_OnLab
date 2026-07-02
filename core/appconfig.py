"""앱 UX 설정 (자세 세트/합격선/타이밍/사운드). config/app_config.json.
웹앱 config.ts 와 동일한 개념. (Engine 이 쓰는 settings.json 과는 분리.)"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "config", "app_config.json")

DEFAULT_APP_CONFIG: dict = {
    "poseSet": ["forward_bend", "side_bend", "overhead_reach", "tpose"],
    "passAccuracy": 85.0,
    "countdownSeconds": 3.0,
    "resultSeconds": 3.0,
    "holdSecondsOverride": None,
    "sound": True,
    "voice": True,
    "adminPin": "4000",  # 관리자 진입 비밀번호 (빈 문자열이면 잠금 해제)
    "showFps": False,    # 좌상단 표시/추론 FPS 진단 오버레이
}


def load_app_config() -> dict:
    cfg = dict(DEFAULT_APP_CONFIG)
    try:
        with open(_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_app_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def reset_app_config() -> None:
    try:
        os.remove(_PATH)
    except FileNotFoundError:
        pass
