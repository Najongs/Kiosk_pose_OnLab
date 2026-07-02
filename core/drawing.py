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
    # Windows (한글 기본: 맑은 고딕)
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/gulim.ttc",
    "C:/Windows/Fonts/batang.ttc",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    # Linux (Noto CJK / 나눔)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
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
    """네온 스타일 스켈레톤: 가산 블렌딩 글로우 + 밝은 본선 + 흰 코어 관절.
    선 굵기는 화면 해상도에 비례해 풀스크린에서도 가늘어 보이지 않는다."""
    kps = pose.keypoints
    h = frame.shape[0]
    lw = max(2, h // 260)  # 본선 굵기 (1080p ≈ 4px)
    lines = []
    joints = []
    for a, b in SKELETON_EDGES:
        if kps[a, 2] >= vis_thresh and kps[b, 2] >= vis_thresh:
            lines.append(((int(kps[a, 0]), int(kps[a, 1])),
                          (int(kps[b, 0]), int(kps[b, 1]))))
    for i in range(len(kps)):
        if kps[i, 2] >= vis_thresh:
            joints.append((int(kps[i, 0]), int(kps[i, 1])))
    if not lines and not joints:
        return

    # 글로우 패스: 사람 주변 ROI 에만 두껍게 그려 블러 후 가산(비용 최소화)
    pts = np.array([p for pair in lines for p in pair] + joints)
    m = lw * 4 + 12
    x1 = max(0, int(pts[:, 0].min()) - m)
    y1 = max(0, int(pts[:, 1].min()) - m)
    x2 = min(frame.shape[1], int(pts[:, 0].max()) + m)
    y2 = min(frame.shape[0], int(pts[:, 1].max()) + m)
    if x2 > x1 and y2 > y1:
        glow = np.zeros((y2 - y1, x2 - x1, 3), dtype=np.uint8)
        for pa, pb in lines:
            cv2.line(glow, (pa[0] - x1, pa[1] - y1), (pb[0] - x1, pb[1] - y1),
                     color, lw * 3, cv2.LINE_AA)
        for p in joints:
            cv2.circle(glow, (p[0] - x1, p[1] - y1), lw * 2 + 2, joint_color, -1,
                       cv2.LINE_AA)
        glow = cv2.blur(glow, (11, 11))
        roi = frame[y1:y2, x1:x2]
        cv2.addWeighted(roi, 1.0, glow, 0.65, 0, roi)

    bright = tuple(min(255, c + 70) for c in color)
    for pa, pb in lines:  # 본선
        cv2.line(frame, pa, pb, bright, lw, cv2.LINE_AA)
    r = lw + 2
    for p in joints:
        cv2.circle(frame, p, r, joint_color, 2, cv2.LINE_AA)          # 색 링
        cv2.circle(frame, p, max(2, r - 3), (255, 255, 255), -1,
                   cv2.LINE_AA)                                        # 흰 코어


def _rounded_shape(canvas: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                   r: int, color, thickness: int) -> None:
    """둥근 모서리 사각형 (filled: thickness=-1, 외곽선: >0)."""
    r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    if r == 0:
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        return
    if thickness < 0:
        cv2.rectangle(canvas, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(canvas, (x1, y1 + r), (x2, y2 - r), color, -1)
    else:
        cv2.line(canvas, (x1 + r, y1), (x2 - r, y1), color, thickness, cv2.LINE_AA)
        cv2.line(canvas, (x1 + r, y2), (x2 - r, y2), color, thickness, cv2.LINE_AA)
        cv2.line(canvas, (x1, y1 + r), (x1, y2 - r), color, thickness, cv2.LINE_AA)
        cv2.line(canvas, (x2, y1 + r), (x2, y2 - r), color, thickness, cv2.LINE_AA)
    corners = [((x1 + r, y1 + r), 180), ((x2 - r, y1 + r), 270),
               ((x2 - r, y2 - r), 0), ((x1 + r, y2 - r), 90)]
    for (cx, cy), ang in corners:
        cv2.ellipse(canvas, (cx, cy), (r, r), ang, 0, 90, color, thickness, cv2.LINE_AA)


def panel(frame: np.ndarray, x1, y1, x2, y2, radius: int = 14,
          color=(18, 20, 32), alpha: float = 0.62,
          border=None, border_thickness: int = 2) -> None:
    """반투명 둥근 패널 (+선택적 외곽선). HUD 의 기본 배경 요소."""
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2 = min(frame.shape[1], int(x2))
    y2 = min(frame.shape[0], int(y2))
    if x2 <= x1 or y2 <= y1:
        return
    sub = frame[y1:y2, x1:x2]
    h, w = sub.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    _rounded_shape(mask, 0, 0, w - 1, h - 1, radius, 255, -1)
    overlay = np.full_like(sub, color, dtype=np.uint8)
    blended = cv2.addWeighted(overlay, alpha, sub, 1 - alpha, 0)
    np.copyto(sub, blended, where=(mask[..., None] > 0))
    if border is not None:
        _rounded_shape(frame, x1, y1, x2 - 1, y2 - 1, radius, border,
                       border_thickness)


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
              fg=(0, 210, 0), bg=(52, 56, 72), pass_ratio: float | None = None) -> None:
    """알약(pill) 모양 게이지. pass_ratio 를 주면 합격선 눈금을 표시한다."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    ratio = max(0.0, min(1.0, ratio))
    r = h // 2
    _rounded_shape(frame, x, y, x + w, y + h, r, bg, -1)
    fill = int(w * ratio)
    if fill > 0:
        _rounded_shape(frame, x, y, x + max(fill, min(h, w)), y + h, r, fg, -1)
    if pass_ratio is not None and 0.0 < pass_ratio < 1.0:
        px = x + int(w * pass_ratio)
        cv2.line(frame, (px, y - 3), (px, y + h + 3), (235, 240, 250), 2, cv2.LINE_AA)
    _rounded_shape(frame, x, y, x + w, y + h, r, (150, 158, 178), 1)


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
    """텍스트 여러 개를 한 번의 PIL 패스로 렌더. 새 BGR 배열 반환.
    풀프레임 색변환(BGR↔RGB) 2회를 아끼기 위해 BGR 버퍼를 그대로 PIL 에
    올리고 색만 뒤집어 그린다(고해상도에서 수 ms 절약)."""
    if not items:
        return frame_bgr
    img = Image.fromarray(frame_bgr)  # BGR 을 RGB 인 척 취급
    draw = ImageDraw.Draw(img)
    for it in items:
        font = get_font(it.size)
        fill = (it.color[2], it.color[1], it.color[0])
        stroke_fill = (it.stroke_color[2], it.stroke_color[1], it.stroke_color[0])
        draw.text(it.xy, it.text, font=font, fill=fill, anchor=it.anchor,
                  stroke_width=it.stroke, stroke_fill=stroke_fill)
    return np.array(img)
