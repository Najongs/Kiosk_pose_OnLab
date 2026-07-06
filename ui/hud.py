"""게임 공용 HUD 프리미티브 (Qt 비의존, cv2/PIL만).

renderer.py 에서 추출 — 스트레칭/대결뿐 아니라 모든 게임 화면이
등급 배지·메시지 필·진행 도트·컨페티·카운트다운 링을 공유한다.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from core.drawing import TextItem, ellipsize, panel, text_width
from core.i18n import en


def grade_of(score: float) -> tuple[str, tuple[int, int, int]]:
    """점수 → 등급 배지 (문자, RGB)."""
    if score >= 95:
        return "S", (255, 215, 90)
    if score >= 85:
        return "A", (120, 255, 140)
    if score >= 70:
        return "B", (120, 190, 255)
    return "C", (200, 205, 220)


def next_grade_gap(score: float) -> str | None:
    """다음 등급까지 남은 점수 문구 — 재도전을 부르는 근접 목표.
    (호기심/불확실성이 자발적 재플레이의 최강 예측자 — CHI 2024, 레퍼런스 조사 D2)"""
    for threshold, name in ((70, "B"), (85, "A"), (95, "S")):
        if score < threshold:
            gap = threshold - score
            if gap <= 15:  # 손에 닿을 듯할 때만 (멀면 오히려 낙담)
                return f"{name} 등급까지 {gap:.0f}점!"
            return None
    return None


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


SUB_COLOR = (168, 178, 198)  # 영어 보조 표기 공용 색 (RGB — 은은한 회청)


def msg_pill(frame: np.ndarray, texts: list[TextItem], msg: str, cy: int,
             size: int, color=(255, 255, 255),
             sub: str | None = "auto") -> None:
    """텍스트 폭에 맞춘 둥근 필 패널 + 중앙 텍스트. 길면 폰트 축소 후 말줄임.

    sub: 영어 보조 표기 한 줄(작게, 아래). 기본 "auto" 는 core.i18n 사전에서
    자동으로 찾고, 없으면 한국어만 표시한다. None 이면 강제로 끈다."""
    h, w = frame.shape[:2]
    if sub == "auto":
        sub = en(msg)
    s = size
    max_w = int(w * 0.86)
    while s > 14 and text_width(msg, s) > max_w:
        s -= 2
    msg = ellipsize(msg, s, max_w)
    tw = text_width(msg, s)
    pad_x = int(s * 0.9)
    pad_y = int(s * 0.55)
    if not sub:
        y1, y2 = cy - s // 2 - pad_y, cy + s // 2 + pad_y
        panel(frame, w // 2 - tw // 2 - pad_x, y1, w // 2 + tw // 2 + pad_x, y2,
              radius=(y2 - y1) // 2, color=(14, 16, 26), alpha=0.55)
        texts.append(TextItem(msg, (w // 2, cy), s, color, anchor="mm"))
        return
    # 2줄 필: 한국어(주) 위 + 영어(보조, 55% 크기) 아래 — 필은 cy 중심 유지
    ss = max(13, int(s * 0.55))
    sub = ellipsize(sub, ss, max_w)
    gap = max(3, s // 8)
    tw = max(tw, text_width(sub, ss))
    total = s + gap + ss
    y1 = cy - total // 2 - pad_y
    y2 = cy + total - total // 2 + pad_y
    panel(frame, w // 2 - tw // 2 - pad_x, y1, w // 2 + tw // 2 + pad_x, y2,
          radius=min(int(s * 0.8), (y2 - y1) // 2), color=(14, 16, 26),
          alpha=0.55)
    cy_main = cy - total // 2 + s // 2
    texts.append(TextItem(msg, (w // 2, cy_main), s, color, anchor="mm"))
    texts.append(TextItem(sub, (w // 2, cy_main + s // 2 + gap + ss // 2), ss,
                          SUB_COLOR, anchor="mm", stroke=1))


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


class TrailTracker:
    """빠르게 움직이는 관절(손목·머리)의 잔상 궤적 — 워커 렌더 클로저가 소유.

    표시 좌표로 스케일된 포즈를 update() 하고, compose 직전에 draw() 하면
    최근 위치들이 색이 옅어지며 이어지는 모션 트레일이 그려진다."""

    def __init__(self, joints: tuple[int, ...] = (0, 15, 16), maxlen: int = 9,
                 color=(160, 231, 127)):
        from collections import deque
        self.joints = joints
        self.color = color
        self._hist: "deque[dict[int, tuple[int, int]]]" = deque(maxlen=maxlen)

    def update(self, pose) -> None:
        if pose is None:
            self._hist.clear()  # 사람이 사라지면 궤적도 끊는다
            return
        kp = pose.keypoints
        pts = {j: (int(kp[j, 0]), int(kp[j, 1]))
               for j in self.joints if j < len(kp) and kp[j, 2] >= 0.3}
        self._hist.append(pts)

    def draw(self, frame: np.ndarray) -> None:
        n = len(self._hist)
        if n < 2:
            return
        h = frame.shape[0]
        for i in range(n - 1):
            a, b = self._hist[i], self._hist[i + 1]
            k = (i + 1) / n  # 오래된 것일수록 옅게·가늘게
            c = tuple(int(v * k * 0.85) for v in self.color)
            lw = max(1, int((h // 260) * k * 2))
            for j in self.joints:
                if j in a and j in b:
                    # 정지 상태의 미세 떨림은 그리지 않는다 (지저분함 방지)
                    if abs(a[j][0] - b[j][0]) + abs(a[j][1] - b[j][1]) > 6:
                        cv2.line(frame, a[j], b[j], c, lw, cv2.LINE_AA)


_spot_cache: dict = {"key": None, "mask": None}


def spotlight(frame: np.ndarray, cx: int, cy: int, rx: int, ry: int,
              dim: float = 0.30) -> None:
    """플레이어 주변만 밝게, 바깥은 어둡게 — 무대 조명 효과.
    사람 위치는 프레임 간 거의 안 변하므로 마스크를 48px 그리드로 양자화해
    캐시한다 (재사용 시 프레임당 비용은 곱 1회 = 비네트 수준)."""
    h, w = frame.shape[:2]
    g = 48
    key = (w, h, cx // g, cy // g, rx // g, ry // g, dim)
    if _spot_cache["key"] != key:
        sw, sh = max(2, w // 4), max(2, h // 4)
        mask = np.full((sh, sw), int(255 * (1.0 - dim)), dtype=np.uint8)
        cv2.ellipse(mask, (cx // 4, cy // 4),
                    (max(4, rx // 4), max(4, ry // 4)),
                    0, 0, 360, 255, -1)
        mask = cv2.blur(mask, (31, 31))
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        _spot_cache["mask"] = np.ascontiguousarray(
            mask[..., None].repeat(3, axis=2))
        _spot_cache["key"] = key
    cv2.multiply(frame, _spot_cache["mask"], dst=frame, scale=1.0 / 255.0)


def stage_light(frame: np.ndarray, primary, active: bool) -> None:
    """플레이 중이면 플레이어 스포트라이트, 아니면 비네트만 — 무대에 선 느낌."""
    if active and primary is not None:
        x1, y1, x2, y2 = primary.bbox
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        rx = int(max(80, (x2 - x1) * 0.85))
        ry = int(max(120, (y2 - y1) * 0.65))
        spotlight(frame, cx, cy, rx, ry)
    else:
        vignette(frame)


def splash_text(texts: list[TextItem], w: int, h: int, msg: str,
                age: float, color=(255, 230, 90),
                sub: str | None = "auto") -> None:
    """상태 전환 순간의 대형 스플래시("시작!") — 크게 떴다가 안착하며 사라짐.
    sub: 영어 보조 표기 (기본 auto = i18n 사전 자동)."""
    if age < 0 or age > 0.7:
        return
    if sub == "auto":
        sub = en(msg)
    k = age / 0.7
    size = int(max(80, h // 5) * (1.45 - 0.45 * min(1.0, k * 2)))
    fade = 1.0 - max(0.0, k - 0.5) * 2
    c = tuple(int(v * fade) for v in color)
    texts.append(TextItem(msg, (w // 2, int(h * 0.42)), size, c,
                          anchor="mm", stroke=6))
    if sub:
        ss = max(24, size // 4)
        sc = tuple(int(v * fade) for v in SUB_COLOR)
        texts.append(TextItem(sub, (w // 2, int(h * 0.42) + size // 2 + ss),
                              ss, sc, anchor="mm", stroke=3))


def draw_popups(frame: np.ndarray, texts: list[TextItem], popups: list[dict],
                now: float) -> None:
    """이벤트 순간의 떠오르는 팝업(+1, +Ncm)과 스파크.
    popup: {"text", "x", "y", "at", "color"(RGB)} — 1.1초 동안 떠오르며 사라짐."""
    h = frame.shape[0]
    for p in popups:
        age = now - p["at"]
        if age < 0 or age > 1.1:
            continue
        k = 1.0 - age / 1.1
        x, y = int(p["x"]), int(p["y"] - 70 * age)
        # 스파크: 처음 0.35초 동안 방사형 선
        if age < 0.35:
            u = age / 0.35
            r0, r1 = int(10 + 26 * u), int(22 + 44 * u)
            for i in range(8):
                a = i * math.pi / 4 + 0.4
                c = tuple(int(v * (1 - u)) for v in (90, 220, 255))
                cv2.line(frame,
                         (int(x + r0 * math.cos(a)), int(y + r0 * math.sin(a))),
                         (int(x + r1 * math.cos(a)), int(y + r1 * math.sin(a))),
                         c, 2, cv2.LINE_AA)
        col = tuple(int(v * (0.35 + 0.65 * k)) for v in p.get("color", (255, 230, 90)))
        size = int(max(26, h // 20) * (1.0 + 0.25 * (1 - k)))
        texts.append(TextItem(p["text"], (x, y), size, col, anchor="mm", stroke=4))


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
