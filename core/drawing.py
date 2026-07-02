"""공용 그리기 유틸.

- 스켈레톤/도형은 OpenCV(BGR numpy)로 그린다(빠름).
- 한글 텍스트는 cv2.putText 로 불가하므로 Pillow + Noto Sans CJK KR 로 렌더한다.
  텍스트는 여러 개를 모아 한 번에 렌더(BGR<->PIL 변환 비용 최소화).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .pose_estimator import SKELETON_EDGES, PersonPose

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _find_font() -> str | None:
    env = os.environ.get("ONLAB_FONT")
    if env and os.path.isfile(env):
        return env
    for p in _FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


_FONT_PATH = _find_font()
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def get_font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        if _FONT_PATH:
            _font_cache[size] = ImageFont.truetype(_FONT_PATH, size)
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def draw_skeleton(frame: np.ndarray, pose: PersonPose, vis_thresh: float = 0.3,
                  color=(0, 235, 0), joint_color=(0, 160, 255)) -> None:
    kps = pose.keypoints
    for a, b in SKELETON_EDGES:
        if kps[a, 2] >= vis_thresh and kps[b, 2] >= vis_thresh:
            pa = (int(kps[a, 0]), int(kps[a, 1]))
            pb = (int(kps[b, 0]), int(kps[b, 1]))
            cv2.line(frame, pa, pb, color, 3, cv2.LINE_AA)
    for i in range(len(kps)):
        if kps[i, 2] >= vis_thresh:
            cv2.circle(frame, (int(kps[i, 0]), int(kps[i, 1])), 4, joint_color, -1,
                       cv2.LINE_AA)


def translucent_rect(frame: np.ndarray, x1, y1, x2, y2, color=(20, 20, 20),
                     alpha: float = 0.55) -> None:
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2 = min(frame.shape[1], int(x2))
    y2 = min(frame.shape[0], int(y2))
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    overlay = np.full_like(roi, color, dtype=np.uint8)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def gauge_bar(frame: np.ndarray, x, y, w, h, ratio: float,
              fg=(0, 210, 0), bg=(70, 70, 70)) -> None:
    ratio = max(0.0, min(1.0, ratio))
    cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), bg, -1)
    cv2.rectangle(frame, (int(x), int(y)), (int(x + w * ratio), int(y + h)), fg, -1)
    cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), (200, 200, 200), 1)


@dataclass
class TextItem:
    text: str
    xy: tuple[int, int]
    size: int
    color: tuple[int, int, int] = (255, 255, 255)  # RGB
    anchor: str = "la"  # PIL anchor: la, ma(center-top), mm(center), rs...
    stroke: int = 2
    stroke_color: tuple[int, int, int] = (0, 0, 0)


def draw_texts(frame_bgr: np.ndarray, items: list[TextItem]) -> np.ndarray:
    """텍스트 여러 개를 한 번의 PIL 변환으로 렌더. 새 BGR 배열 반환."""
    if not items:
        return frame_bgr
    img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    for it in items:
        font = get_font(it.size)
        draw.text(it.xy, it.text, font=font, fill=it.color, anchor=it.anchor,
                  stroke_width=it.stroke, stroke_fill=it.stroke_color)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
