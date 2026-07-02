"""게임 공용 HUD 프리미티브 (Qt 비의존, cv2/PIL만).

renderer.py 에서 추출 — 스트레칭/대결뿐 아니라 모든 게임 화면이
등급 배지·메시지 필·진행 도트·컨페티·카운트다운 링을 공유한다.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from core.drawing import TextItem, ellipsize, panel, text_width


def grade_of(score: float) -> tuple[str, tuple[int, int, int]]:
    """점수 → 등급 배지 (문자, RGB)."""
    if score >= 95:
        return "S", (255, 215, 90)
    if score >= 85:
        return "A", (120, 255, 140)
    if score >= 70:
        return "B", (120, 190, 255)
    return "C", (200, 205, 220)


def acc_colors(accuracy: float, pass_accuracy: float):
    """(cv2 BGR bar 색, PIL RGB 텍스트 색) 반환."""
    if accuracy >= pass_accuracy:
        return (0, 210, 0), (120, 255, 120)
    if accuracy >= pass_accuracy * 0.6:
        return (0, 200, 220), (255, 230, 120)
    return (60, 80, 235), (255, 140, 140)


def dots_x0(total: int, w: int) -> int | None:
    """진행 도트의 시작 x (없으면 None) — 상단바 텍스트 겹침 방지 계산용."""
    if total < 2 or total > 20:
        return None
    return w - 28 - (total - 1) * 20


def msg_pill(frame: np.ndarray, texts: list[TextItem], msg: str, cy: int,
             size: int, color=(255, 255, 255)) -> None:
    """텍스트 폭에 맞춘 둥근 필 패널 + 중앙 텍스트. 길면 폰트 축소 후 말줄임."""
    h, w = frame.shape[:2]
    s = size
    max_w = int(w * 0.86)
    while s > 14 and text_width(msg, s) > max_w:
        s -= 2
    msg = ellipsize(msg, s, max_w)
    tw = text_width(msg, s)
    pad_x = int(s * 0.9)
    pad_y = int(s * 0.55)
    y1, y2 = cy - s // 2 - pad_y, cy + s // 2 + pad_y
    panel(frame, w // 2 - tw // 2 - pad_x, y1, w // 2 + tw // 2 + pad_x, y2,
          radius=(y2 - y1) // 2, color=(14, 16, 26), alpha=0.55)
    texts.append(TextItem(msg, (w // 2, cy), s, color, anchor="mm"))


def progress_dots(frame: np.ndarray, index: int, total: int, w: int, h: int) -> None:
    """상단바 우측: 진행 도트 (완료=액센트, 현재=밝게, 남음=어둡게)."""
    x0 = dots_x0(total, w)
    if x0 is None:
        return
    gap = 20
    cy = int(h * 0.055)
    for i in range(total):
        cx = x0 + i * gap
        if i < index:
            cv2.circle(frame, (cx, cy), 5, (160, 231, 127), -1, cv2.LINE_AA)
        elif i == index:
            cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 8, (160, 231, 127), 1, cv2.LINE_AA)
        else:
            cv2.circle(frame, (cx, cy), 4, (96, 102, 124), -1, cv2.LINE_AA)


CONFETTI_COLORS = [(80, 200, 255), (160, 231, 127), (255, 168, 74),
                   (196, 110, 255), (120, 240, 255)]  # BGR


def confetti(frame: np.ndarray, anim_t: float | None, n: int = 46) -> None:
    """결과 화면용 떨어지는 컨페티 (결정적 의사난수 + anim_t 로 애니메이션)."""
    if anim_t is None:
        return
    h, w = frame.shape[:2]

    def rand(k: int, salt: float) -> float:
        v = math.sin(k * 12.9898 + salt) * 43758.5453
        return v - math.floor(v)

    for k in range(n):
        r1, r2, r3 = rand(k, 1.1), rand(k, 7.7), rand(k, 23.3)
        speed = 0.22 + 0.33 * r2
        y = ((r3 + anim_t * speed) % 1.15) - 0.075
        x = r1 + 0.025 * math.sin(anim_t * 2.6 + k)
        cxp, cyp = int(x * w), int(y * h)
        size = 3 + int(4 * r2)
        a = anim_t * (2.5 + 2 * r1) + k
        dx, dy = int(size * math.cos(a)), int(size * math.sin(a))
        cv2.line(frame, (cxp - dx, cyp - dy), (cxp + dx, cyp + dy),
                 CONFETTI_COLORS[k % len(CONFETTI_COLORS)], 3, cv2.LINE_AA)


def countdown_ring(frame: np.ndarray, cx: int, cy: int, r: int,
                   remaining: float) -> None:
    """매초 한 바퀴 도는 카운트다운 링 (숫자는 호출자가 그린다)."""
    frac = float(remaining) % 1.0
    cv2.circle(frame, (cx, cy), r, (70, 76, 96), 6, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (r, r), -90, 0, int(360 * frac),
                (160, 231, 127), 6, cv2.LINE_AA)
