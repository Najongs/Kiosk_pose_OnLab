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
    """매초 한 바퀴 도는 카운트다운 링 + 시계 눈금 + 초 경계 펄스."""
    frac = float(remaining) % 1.0
    # 바깥 눈금 12개 (시계 필)
    for k in range(12):
        a = math.radians(k * 30 - 90)
        r1, r2 = r + 10, r + 10 + (8 if k % 3 == 0 else 4)
        cv2.line(frame,
                 (int(cx + r1 * math.cos(a)), int(cy + r1 * math.sin(a))),
                 (int(cx + r2 * math.cos(a)), int(cy + r2 * math.sin(a))),
                 (96, 108, 132), 2, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), r, (70, 76, 96), 6, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (r, r), -90, 0, int(360 * frac),
                (160, 231, 127), 6, cv2.LINE_AA)
    # 초가 바뀌는 순간(frac 이 1 근처) 링이 살짝 번쩍
    if frac > 0.85:
        k = (frac - 0.85) / 0.15
        cv2.circle(frame, (cx, cy), int(r + 6 + 10 * k), (160, 231, 127), 2,
                   cv2.LINE_AA)
    # 진행 끝점 발광 점
    a = math.radians(360 * frac - 90)
    cv2.circle(frame, (int(cx + r * math.cos(a)), int(cy + r * math.sin(a))),
               7, (255, 255, 255), -1, cv2.LINE_AA)


# ---- 게임 연출 프리미티브 ----

_vignette_cache: dict[tuple[int, int], np.ndarray] = {}


def vignette(frame: np.ndarray, strength: float = 0.32) -> None:
    """가장자리를 어둡게 — 시선을 중앙으로 모으는 시네마틱 연출.
    마스크는 해상도별 1회 생성 후 캐시(프레임당 곱 1회)."""
    h, w = frame.shape[:2]
    mask = _vignette_cache.get((w, h))
    if mask is None:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx = (xx / w - 0.5) * 2.0
        ny = (yy / h - 0.5) * 2.0
        d = np.sqrt(nx * nx + ny * ny) / math.sqrt(2.0)
        m = 1.0 - strength * np.clip(d - 0.45, 0.0, 1.0) / 0.55
        mask = (np.clip(m, 0.0, 1.0) * 255).astype(np.uint8)[..., None]
        mask = np.repeat(mask, 3, axis=2)
        _vignette_cache[(w, h)] = mask
    cv2.multiply(frame, mask, dst=frame, scale=1.0 / 255.0)


def corner_brackets(frame: np.ndarray, color=(160, 231, 127),
                    anim_t: float | None = None) -> None:
    """화면 네 모서리의 HUD 브래킷 — 은은한 호흡 펄스."""
    h, w = frame.shape[:2]
    m = max(14, h // 44)          # 모서리 여백
    s = max(26, h // 18)          # 브래킷 팔 길이
    th = max(2, h // 300)
    if anim_t is not None:
        k = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(anim_t * 2.4))
        color = tuple(int(c * k) for c in color)
    for cx, cy, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1),
                           (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        cv2.line(frame, (cx, cy), (cx + dx * s, cy), color, th, cv2.LINE_AA)
        cv2.line(frame, (cx, cy), (cx, cy + dy * s), color, th, cv2.LINE_AA)


def top_accent(frame: np.ndarray, y: int, anim_t: float | None = None) -> None:
    """상단바 아래 액센트 라인 — 좌→우로 흐르는 하이라이트."""
    h, w = frame.shape[:2]
    cv2.line(frame, (0, y), (w, y), (72, 120, 96), 1, cv2.LINE_AA)
    if anim_t is None:
        return
    cx = int(((anim_t % 3.0) / 3.0) * (w + 240)) - 120
    for dx in range(-90, 91, 6):
        k = 1.0 - abs(dx) / 90.0
        x = cx + dx
        if 0 <= x < w:
            cv2.line(frame, (x, y - 1), (x + 5, y - 1),
                     (int(96 + 100 * k), int(160 + 80 * k), int(120 + 60 * k)),
                     2, cv2.LINE_AA)


def burst_rays(frame: np.ndarray, cx: int, cy: int, anim_t: float | None,
               color=(60, 200, 255), n: int = 12, r0: int = 70,
               r1: int = 999) -> None:
    """결과 연출용 회전 광선 — 점수 뒤에서 천천히 돈다."""
    if anim_t is None:
        return
    h, w = frame.shape[:2]
    r1 = min(r1, int(max(w, h) * 0.75))
    base = anim_t * 0.35
    overlay_pts = []
    for k in range(n):
        a = base + k * (2 * math.pi / n)
        half = 0.028 + 0.012 * math.sin(anim_t * 1.7 + k)
        p0 = (int(cx + r0 * math.cos(a)), int(cy + r0 * math.sin(a)))
        p1 = (int(cx + r1 * math.cos(a - half)), int(cy + r1 * math.sin(a - half)))
        p2 = (int(cx + r1 * math.cos(a + half)), int(cy + r1 * math.sin(a + half)))
        overlay_pts.append(np.array([p0, p1, p2], dtype=np.int32))
    overlay = frame.copy()
    for pts in overlay_pts:
        cv2.fillPoly(overlay, [pts], color, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.10, frame, 0.90, 0, frame)


def expanding_rings(frame: np.ndarray, cx: int, cy: int, age: float,
                    color=(60, 200, 255), period: float = 0.5,
                    count: int = 3) -> None:
    """신호/타격 순간의 확산 링 — age(초)에 따라 커지며 사라진다."""
    h, w = frame.shape[:2]
    rmax = int(max(w, h) * 0.6)
    for k in range(count):
        t = age - k * period * 0.4
        if t < 0:
            continue
        u = (t % period) / period if k == 0 else min(1.0, t / period)
        if k > 0 and t > period:
            continue
        r = int(40 + u * rmax)
        alpha = max(0.0, 1.0 - u)
        c = tuple(int(v * alpha) for v in color)
        cv2.circle(frame, (cx, cy), r, c, max(2, int(6 * alpha)), cv2.LINE_AA)
