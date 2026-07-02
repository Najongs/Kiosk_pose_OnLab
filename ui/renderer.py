"""UI 화면 합성 (Qt 비의존).

세션 상태(SessionState)와 현재 포즈를 받아 키오스크 화면 한 장(BGR numpy)을
합성한다. Qt 창은 이 결과를 그대로 표시만 하면 되고, 헤드리스에서는 이 함수의
출력을 PNG 로 저장해 그대로 검증할 수 있다.
"""

from __future__ import annotations

import os

import numpy as np

import cv2

from core.drawing import (
    TextItem,
    draw_skeleton,
    draw_texts,
    ellipsize,
    gauge_bar,
    panel,
    text_width,
    translucent_rect,
)
from core.pose_estimator import PersonPose
import math

from ui.hud import (
    acc_colors as _acc_colors,
    confetti as _confetti,
    countdown_ring,
    dots_x0 as _dots_x0,
    grade_of as _grade_of,
    msg_pill as _msg_pill,
    progress_dots as _progress_dots,
)

from core.refs import REF_VIS, get_ref3d
from core.session import SessionState, State
from core.versus import VersusState, VState

_EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "examples")
_EXAMPLE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_examples_cache: dict[str, list[np.ndarray]] = {}
EXAMPLE_STEP_SECONDS = 1.2  # 연속동작 예시 전환 주기


def example_images(pose_name: str) -> list[np.ndarray]:
    """동작 예시 이미지 목록. `<pose>.png` 한 장 또는 `<pose>_1.png`,
    `<pose>_2.png`… 처럼 여러 장(연속동작)을 지원한다. 없으면 빈 리스트."""
    if pose_name in _examples_cache:
        return _examples_cache[pose_name]
    import glob as _glob

    from core.frame_source import imread_unicode  # 비ASCII 경로 안전
    paths: list[str] = []
    for ext in _EXAMPLE_EXTS:
        p = os.path.join(_EXAMPLES_DIR, pose_name + ext)
        if os.path.isfile(p):
            paths.append(p)
            break
    step_paths: list[str] = []
    for ext in _EXAMPLE_EXTS:
        step_paths.extend(_glob.glob(os.path.join(_EXAMPLES_DIR, f"{pose_name}_*{ext}")))
    paths.extend(sorted(step_paths))
    imgs = [im for im in (imread_unicode(p) for p in paths) if im is not None]
    _examples_cache[pose_name] = imgs
    return imgs


def example_image(pose_name: str) -> np.ndarray | None:
    """(호환용) 첫 예시 이미지 또는 None."""
    imgs = example_images(pose_name)
    return imgs[0] if imgs else None


# 베이크된 캐릭터 턴테이블 스프라이트 (tools/bake_character.py 산출물)
_SPRITES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "character", "sprites")
_char_sprites: list[np.ndarray] | None = None
SPRITE_FPS = 12.0


def _load_rgba_seq(pattern: str) -> list[np.ndarray]:
    import glob as _glob
    imgs = []
    for p in sorted(_glob.glob(pattern)):
        try:
            data = np.fromfile(p, dtype=np.uint8)
            im = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        except OSError:
            im = None
        if im is not None and im.ndim == 3 and im.shape[2] == 4:
            imgs.append(im)
    return imgs


def character_sprites() -> list[np.ndarray]:
    """RGBA 턴테이블 프레임 목록 (없으면 빈 리스트)."""
    global _char_sprites
    if _char_sprites is None:
        _char_sprites = _load_rgba_seq(os.path.join(_SPRITES_DIR, "turn_*.png"))
    return _char_sprites


_pose_sprites_cache: dict[str, list[np.ndarray]] = {}


def pose_sprites(pose_name: str) -> list[np.ndarray]:
    """자세 시연 시퀀스 (sprites/<자세>/frame_*.png) — 캐릭터가 자세를 취함."""
    if pose_name not in _pose_sprites_cache:
        _pose_sprites_cache[pose_name] = _load_rgba_seq(
            os.path.join(_SPRITES_DIR, pose_name, "frame_*.png"))
    return _pose_sprites_cache[pose_name]


def _fit_image_alpha(frame: np.ndarray, rgba: np.ndarray,
                     x: int, y: int, w: int, h: int) -> None:
    """RGBA 스프라이트를 박스에 맞춰 알파 합성."""
    ih0, iw0 = rgba.shape[:2]
    scale = min(w / iw0, h / ih0)
    nw, nh = max(1, int(iw0 * scale)), max(1, int(ih0 * scale))
    resized = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA)
    ox, oy = x + (w - nw) // 2, y + (h - nh) // 2
    roi = frame[oy:oy + nh, ox:ox + nw]
    a = resized[..., 3:4].astype(np.float32) / 255.0
    roi[:] = (resized[..., :3].astype(np.float32) * a
              + roi.astype(np.float32) * (1.0 - a)).astype(np.uint8)


def _fit_image(frame: np.ndarray, img: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    if img is None:
        return
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    ih0, iw0 = img.shape[:2]
    scale = min(w / iw0, h / ih0)
    nw, nh = max(1, int(iw0 * scale)), max(1, int(ih0 * scale))
    resized = cv2.resize(img, (nw, nh))
    ox, oy = x + (w - nw) // 2, y + (h - nh) // 2
    frame[oy:oy + nh, ox:ox + nw] = resized


# 캐릭터 기본(서있는) 자세 — 가이드 박스 정규화 좌표
_BASE_STAND = {
    0: (0.50, 0.06),
    11: (0.38, 0.22), 12: (0.62, 0.22),
    13: (0.34, 0.40), 14: (0.66, 0.40),
    15: (0.32, 0.56), 16: (0.68, 0.56),
    23: (0.43, 0.52), 24: (0.57, 0.52),
    25: (0.42, 0.74), 26: (0.58, 0.74),
    27: (0.41, 0.94), 28: (0.59, 0.94),
}
_CHAR_LIMBS = [(11, 13), (13, 15), (12, 14), (14, 16),
               (23, 25), (25, 27), (24, 26), (26, 28)]
CHAR_CYCLE_SECONDS = 3.2  # 서있기→목표자세→유지→복귀 한 사이클


def _draw_character(frame: np.ndarray, ref: list[list[float]],
                    ix: int, iy: int, iw: int, ih: int,
                    anim_t: float | None) -> None:
    """참조 스켈레톤을 향해 반복 트윈하는 미니 캐릭터 (머리+몸통+팔다리)."""
    if anim_t is None:
        t = 1.0
    else:
        cyc = (anim_t % CHAR_CYCLE_SECONDS) / CHAR_CYCLE_SECONDS
        if cyc < 0.35:            # 목표 자세로 이동
            u = cyc / 0.35
        elif cyc < 0.75:          # 유지
            u = 1.0
        else:                     # 복귀
            u = 1.0 - (cyc - 0.75) / 0.25
        t = u * u * (3 - 2 * u)   # smoothstep

    def pt(i: int) -> tuple[int, int]:
        bx, by = _BASE_STAND[i]
        if i < len(ref) and ref[i][2] >= REF_VIS:
            x = bx + (ref[i][0] - bx) * t
            y = by + (ref[i][1] - by) * t
        else:  # 참조에 없는 관절은 기본 자세 유지
            x, y = bx, by
        return int(ix + x * iw), int(iy + y * ih)

    lw = max(3, ih // 34)
    body = (127, 231, 160)  # 민트 (BGR)
    dark = (64, 118, 84)
    p11, p12, p23, p24 = pt(11), pt(12), pt(23), pt(24)
    torso = np.array([p11, p12, p24, p23], dtype=np.int32)
    cv2.fillPoly(frame, [torso], (52, 96, 66), cv2.LINE_AA)
    cv2.polylines(frame, [torso], True, body, 2, cv2.LINE_AA)
    for a, b in _CHAR_LIMBS:
        cv2.line(frame, pt(a), pt(b), dark, lw + 3, cv2.LINE_AA)
    for a, b in _CHAR_LIMBS:
        cv2.line(frame, pt(a), pt(b), body, lw, cv2.LINE_AA)
    for i in (13, 14, 15, 16, 25, 26, 27, 28):
        cv2.circle(frame, pt(i), max(2, lw - 1), (235, 255, 240), -1, cv2.LINE_AA)
    hx, hy = pt(0)
    neck = ((p11[0] + p12[0]) // 2, (p11[1] + p12[1]) // 2)
    cv2.line(frame, (hx, hy), neck, dark, lw + 3, cv2.LINE_AA)
    cv2.line(frame, (hx, hy), neck, body, lw, cv2.LINE_AA)
    r = max(5, int(ih * 0.055))
    cv2.circle(frame, (hx, hy), r, body, -1, cv2.LINE_AA)
    cv2.circle(frame, (hx, hy), r, dark, 2, cv2.LINE_AA)


# 3D 기본(서있는) 자세 — MediaPipe world 규약(엉덩이 원점, x 오른쪽, y 아래, 미터)
_BASE3D = {
    0: (0.0, -0.64, 0.04),
    11: (-0.17, -0.44, 0.0), 12: (0.17, -0.44, 0.0),
    13: (-0.23, -0.20, 0.02), 14: (0.23, -0.20, 0.02),
    15: (-0.25, 0.02, 0.06), 16: (0.25, 0.02, 0.06),
    23: (-0.09, 0.0, 0.0), 24: (0.09, 0.0, 0.0),
    25: (-0.10, 0.42, 0.02), 26: (0.10, 0.42, 0.02),
    27: (-0.11, 0.84, 0.0), 28: (0.11, 0.84, 0.0),
}


def _tween_progress(anim_t: float | None) -> float:
    """서있기→목표→유지→복귀 사이클의 smoothstep 진행도."""
    if anim_t is None:
        return 1.0
    cyc = (anim_t % CHAR_CYCLE_SECONDS) / CHAR_CYCLE_SECONDS
    if cyc < 0.35:
        u = cyc / 0.35
    elif cyc < 0.75:
        u = 1.0
    else:
        u = 1.0 - (cyc - 0.75) / 0.25
    return u * u * (3 - 2 * u)


def _draw_character_3d(frame: np.ndarray, ref3d: list[list[float]],
                       ix: int, iy: int, iw: int, ih: int,
                       anim_t: float | None) -> None:
    """3D 월드 좌표 기반 턴테이블 캐릭터 — 좌우로 천천히 돌며 앞뒤 깊이를
    보여줘 2D 착시(팔이 앞인지 뒤인지)를 없앤다. 깊이에 따라 굵기·밝기·
    가림 순서가 달라지고, 바닥 그림자가 방향 기준을 잡아준다."""
    t = _tween_progress(anim_t)
    theta = 0.55 * math.sin((anim_t or 0.0) * 1.05)  # ±31도 턴테이블
    c, s = math.cos(theta), math.sin(theta)

    j3: dict[int, tuple[float, float, float]] = {}
    for i, (bx, by, bz) in _BASE3D.items():
        if i < len(ref3d) and len(ref3d[i]) >= 4 and ref3d[i][3] >= REF_VIS:
            x = bx + (ref3d[i][0] - bx) * t
            y = by + (ref3d[i][1] - by) * t
            z = bz + (ref3d[i][2] - bz) * t
        else:
            x, y, z = bx, by, bz
        j3[i] = (x, y, z)

    # y축 회전 투영. 스케일은 회전 불변 반경으로 고정(프레임 간 출렁임 방지)
    proj: dict[int, tuple[float, float]] = {}
    depth: dict[int, float] = {}
    for i, (x, y, z) in j3.items():
        proj[i] = (x * c + z * s, y)
        depth[i] = -x * s + z * c
    rh = max(math.hypot(x, z) for x, y, z in j3.values()) * 2.0
    ys = [y for _, y, _ in j3.values()]
    ylo, yhi = min(ys), max(ys)
    sc = 0.86 * min(iw / max(rh, 1e-3), ih / max(yhi - ylo, 1e-3))
    cx = ix + iw / 2.0
    cy0 = iy + ih / 2.0 - (ylo + yhi) / 2.0 * sc

    def P(i: int) -> tuple[int, int]:
        return int(cx + proj[i][0] * sc), int(cy0 + proj[i][1] * sc)

    # 바닥 그림자 (방향/공간 기준점)
    gy = int(cy0 + yhi * sc) + max(3, ih // 60)
    cv2.ellipse(frame, (int(cx), gy), (int(iw * 0.30), max(4, ih // 26)),
                0, 0, 360, (10, 12, 18), -1, cv2.LINE_AA)

    dmin = min(depth.values())
    dmax = max(depth.values())
    rng = max(1e-6, dmax - dmin)

    def near_k(d: float) -> float:  # 0=멀리, 1=가까이
        return (d - dmin) / rng

    def shade(base: tuple, k: float) -> tuple:
        f = 0.55 + 0.55 * k
        return tuple(min(255, int(v * f)) for v in base)

    body = (127, 231, 160)  # 민트 (BGR)
    lw = max(3, ih // 34)
    items: list[tuple[float, str, object]] = []
    for a, b in _CHAR_LIMBS:
        items.append(((depth[a] + depth[b]) / 2, "limb", (a, b)))
    items.append(((depth[11] + depth[12] + depth[23] + depth[24]) / 4, "torso", None))
    items.append((depth[0], "head", None))
    items.sort(key=lambda e: e[0])  # 먼 것부터 (painter's algorithm)

    for d, kind, data in items:
        k = near_k(d)
        col = shade(body, k)
        dark = shade((52, 96, 66), k)
        hi = shade((208, 255, 224), k)  # 좌상단 광원 하이라이트 (원통/구 셰이딩)
        if kind == "limb":
            a, b = data  # type: ignore[misc]
            width = max(3, int(lw * (0.7 + 0.6 * k)))
            pa, pb = P(a), P(b)
            off = max(1, width // 3)
            cv2.line(frame, pa, pb, dark, width + 4, cv2.LINE_AA)
            cv2.line(frame, pa, pb, col, width, cv2.LINE_AA)
            cv2.line(frame, (pa[0] - off, pa[1] - off), (pb[0] - off, pb[1] - off),
                     hi, max(2, int(width * 0.4)), cv2.LINE_AA)
            cv2.circle(frame, pb, width // 2 + 2, col, -1, cv2.LINE_AA)  # 관절 구
            cv2.circle(frame, (pb[0] - off, pb[1] - off), max(2, width // 4), hi,
                       -1, cv2.LINE_AA)
        elif kind == "torso":
            quad = np.array([P(11), P(12), P(24), P(23)], dtype=np.int32)
            cv2.fillPoly(frame, [quad], shade((44, 82, 56), k), cv2.LINE_AA)
            cv2.polylines(frame, [quad], True, col, 2, cv2.LINE_AA)
            neck = ((P(11)[0] + P(12)[0]) // 2, (P(11)[1] + P(12)[1]) // 2)
            hip_mid = ((P(23)[0] + P(24)[0]) // 2, (P(23)[1] + P(24)[1]) // 2)
            cv2.line(frame, neck, hip_mid, shade((64, 118, 82), k), lw * 2,
                     cv2.LINE_AA)  # 몸통 중앙 음영 밴드
            cv2.line(frame, P(0), neck, col, lw, cv2.LINE_AA)
        else:  # head — 구 셰이딩
            r = max(5, int(ih * 0.055 * (0.85 + 0.3 * k)))
            p0 = P(0)
            cv2.circle(frame, p0, r, col, -1, cv2.LINE_AA)
            cv2.circle(frame, (p0[0] - r // 3, p0[1] - r // 3), max(2, r // 3),
                       hi, -1, cv2.LINE_AA)
            cv2.circle(frame, p0, r, shade((60, 118, 84), k), 2, cv2.LINE_AA)


def draw_guide(frame: np.ndarray, pose_name: str,
               ref_norm: list[list[float]] | None,
               anim_t: float | None = None,
               style: str = "image") -> None:
    """목표 자세 예시를 화면 왼쪽 박스에 그린다.
    style='image'(기본): 예시 이미지 > 움직이는 캐릭터(참조) > 빈 박스.
    style='character': 참조가 있으면 캐릭터 우선.
    예시가 여러 장이면(연속동작) anim_t 기준으로 주기 순환 + 단계 점 표시."""
    h, w = frame.shape[:2]
    bw = int(w * 0.18)
    bh = int(bw * 1.3)
    bx = int(w * 0.02)
    by = int(h * 0.30)
    panel(frame, bx, by, bx + bw, by + bh, radius=14, color=(16, 18, 30),
          alpha=0.72, border=(220, 170, 140), border_thickness=2)
    # 좌측 포인트 라인 (액센트)
    cv2.line(frame, (bx + 6, by + 14), (bx + 6, by + bh - 14), (160, 231, 127), 3,
             cv2.LINE_AA)
    pad = int(bw * 0.1)
    ix, iy = bx + pad, by + int(bh * 0.16)
    iw, ih = bw - pad * 2, bh - int(bh * 0.16) - pad

    if style == "mesh3d":
        seq = pose_sprites(pose_name)
        if seq:
            # 자세 시연: 서있기→자세→유지→복귀 사이클로 프레임 선택
            t = _tween_progress(anim_t)
            _fit_image_alpha(frame, seq[int(round(t * (len(seq) - 1)))],
                             ix, iy, iw, ih)
            return
        sprites = character_sprites()  # 자세 시퀀스 없으면 턴테이블
        if sprites:
            idx = int((anim_t or 0) * SPRITE_FPS) % len(sprites)
            _fit_image_alpha(frame, sprites[idx], ix, iy, iw, ih)
            return
        style = "character"  # 스프라이트 없으면 절차적 캐릭터로

    imgs = example_images(pose_name)
    ref3d = get_ref3d(pose_name)
    use_char = (bool(ref_norm) or ref3d is not None) and (
        style == "character" or not imgs)
    if use_char:
        if ref3d is not None:
            _draw_character_3d(frame, ref3d, ix, iy, iw, ih, anim_t)
        else:
            _draw_character(frame, ref_norm, ix, iy, iw, ih, anim_t)
    elif imgs:
        idx = 0
        if len(imgs) > 1 and anim_t is not None:
            idx = int(anim_t / EXAMPLE_STEP_SECONDS) % len(imgs)
        _fit_image(frame, imgs[idx], ix, iy, iw, ih)
        if len(imgs) > 1:  # 연속동작 단계 점
            n = len(imgs)
            cy = by + bh - int(pad * 0.6)
            cx0 = bx + bw // 2 - (n - 1) * 9
            for i in range(n):
                c = (160, 231, 127) if i == idx else (110, 116, 138)
                cv2.circle(frame, (cx0 + i * 18, cy), 4 if i == idx else 3, c, -1,
                           cv2.LINE_AA)


def compose(frame: np.ndarray, primary: PersonPose | None, state: SessionState,
            pass_accuracy: float = 85.0,
            ref_norm: list[list[float]] | None = None,
            anim_t: float | None = None,
            guide_style: str = "image") -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []

    if primary is not None:
        # 합격 범위에 들어오면 스켈레톤이 골드로 변한다 (즉각적인 성공 피드백)
        passing = (state.state == State.SCORING and state.accuracy is not None
                   and state.accuracy >= pass_accuracy)
        draw_skeleton(frame, primary,
                      color=(60, 200, 255) if passing else (0, 235, 0),
                      joint_color=(90, 220, 255) if passing else (0, 160, 255))

    if (state.target_pose is not None and guide_style != "none"
            and state.state in (State.COUNTDOWN, State.SCORING)):
        draw_guide(frame, state.target_pose.name, ref_norm, anim_t, guide_style)
        # 박스 상단 라벨 (좌측). 예시 이미지도 참조도 없으면 안내 문구
        texts.append(TextItem("따라해 보세요", (int(w * 0.02 + w * 0.09), int(h * 0.335)),
                              max(15, h // 42), (200, 220, 255), anchor="mm"))
        if (not example_images(state.target_pose.name) and not ref_norm
                and get_ref3d(state.target_pose.name) is None):
            # 박스 세로 중앙에 (테두리에 걸치지 않게)
            box_cy = int(h * 0.30 + int(w * 0.18) * 1.3 * 0.55)
            texts.append(TextItem("예시 준비 중", (int(w * 0.02 + w * 0.09), box_cy),
                                  max(13, h // 50), (150, 160, 180), anchor="mm"))

    # 상단 진행 바(자세 n/N + 자세명 + 진행 도트)
    if state.target_pose is not None:
        translucent_rect(frame, 0, 0, w, int(h * 0.11), color=(14, 16, 26), alpha=0.62)
        cv2.line(frame, (0, int(h * 0.11)), (w, int(h * 0.11)), (72, 120, 96), 1,
                 cv2.LINE_AA)
        small = max(20, h // 28)
        big = max(26, h // 20)
        n_txt = f"자세 {state.pose_index + 1}/{state.pose_total}"
        if state.combo >= 2:
            n_txt += f"  ·  콤보 x{state.combo}"
        texts.append(TextItem(n_txt, (24, int(h * 0.055)), small,
                              (255, 190, 110) if state.combo >= 2 else (200, 220, 255),
                              anchor="lm"))
        # 자세명: 좌측 텍스트/우측 진행 도트와 겹치지 않게 배치 + 말줄임
        name_x = max(int(w * 0.28), 24 + text_width(n_txt, small) + 32)
        dx0 = _dots_x0(state.pose_total, w)
        name_max = (dx0 - 26 if dx0 is not None else w - 40) - name_x
        texts.append(TextItem(
            ellipsize(state.target_pose.display_name, big, max(80, name_max)),
            (name_x, int(h * 0.055)), big, (255, 255, 255), anchor="lm"))
        _progress_dots(frame, state.pose_index, state.pose_total, w, h)

    if state.state == State.IDLE:
        panel(frame, int(w * 0.12), int(h * 0.42), int(w * 0.88), int(h * 0.58),
              radius=20, color=(14, 16, 26), alpha=0.66,
              border=(200, 150, 120), border_thickness=1)
        texts.append(TextItem(state.message, (w // 2, h // 2), max(30, h // 16),
                              (255, 255, 255), anchor="mm"))

    elif state.state == State.COUNTDOWN:
        n = int(np.ceil(state.countdown_remaining or 0))
        # 매초 한 바퀴 도는 링 + 큰 숫자
        r = max(60, h // 6)
        countdown_ring(frame, w // 2, h // 2, r, state.countdown_remaining or 0)
        texts.append(TextItem(str(n), (w // 2, h // 2), max(90, h // 4),
                              (255, 255, 255), anchor="mm", stroke=6))
        _msg_pill(frame, texts, state.message, int(h * 0.80), max(24, h // 22),
                  (220, 235, 255))

    elif state.state == State.SCORING:
        acc = state.accuracy
        # 정확도 게이지(좌측) — 합격선 눈금 포함
        gx, gy, gw, gh = 24, int(h * 0.16), int(w * 0.28), max(22, h // 26)
        panel(frame, gx - 10, gy - int(h * 0.045) - 8, gx + gw + 10, gy + gh + 10,
              radius=12, color=(14, 16, 26), alpha=0.5)
        if acc is not None:
            bar_c, txt_c = _acc_colors(acc, pass_accuracy)
            gauge_bar(frame, gx, gy, gw, gh, acc / 100.0, fg=bar_c,
                      pass_ratio=pass_accuracy / 100.0)
            texts.append(TextItem(f"정확도 {acc:.0f}%", (gx, gy - 8),
                                  max(20, h // 30), txt_c, anchor="lb"))
        else:
            gauge_bar(frame, gx, gy, gw, gh, 0.0, pass_ratio=pass_accuracy / 100.0)
            texts.append(TextItem("정확도 --", (gx, gy - 8), max(20, h // 30),
                                  (220, 220, 220), anchor="lb"))
        # 유지 진행 바(하단)
        hx, hy, hw, hh = int(w * 0.2), int(h * 0.88), int(w * 0.6), max(18, h // 34)
        panel(frame, hx - int(w * 0.055), hy - 10, hx + hw + 14, hy + hh + 10,
              radius=12, color=(14, 16, 26), alpha=0.5)
        gauge_bar(frame, hx, hy, hw, hh, state.hold_progress, fg=(230, 180, 40))
        texts.append(TextItem("유지", (hx - 12, hy + hh // 2), max(18, h // 34),
                              (255, 235, 180), anchor="rm"))
        _msg_pill(frame, texts, state.message, int(h * 0.80), max(22, h // 24))

    elif state.state == State.RESULT:
        panel(frame, int(w * 0.14), int(h * 0.30), int(w * 0.86), int(h * 0.74),
              radius=24, color=(12, 14, 24), alpha=0.68,
              border=(127, 231, 160), border_thickness=2)
        _confetti(frame, anim_t)
        score = state.last_score or 0.0
        grade, grade_rgb = _grade_of(score)
        texts.append(TextItem("완료!", (w // 2, int(h * 0.40)), max(34, h // 14),
                              (120, 255, 140), anchor="mm"))
        score_fs = max(70, h // 6)
        score_txt = f"{score:.0f}점"
        texts.append(TextItem(score_txt, (w // 2, int(h * 0.55)),
                              score_fs, (255, 255, 255), anchor="mm", stroke=5))
        # 점수 폭을 재서 좌(콤보)/우(등급)를 겹치지 않게 배치
        half = text_width(score_txt, score_fs) // 2
        texts.append(TextItem(grade, (w // 2 + half + int(w * 0.05), int(h * 0.52)),
                              max(60, h // 8), grade_rgb, anchor="mm", stroke=5))
        if state.combo >= 2:
            texts.append(TextItem(f"콤보 x{state.combo}  +{state.combo_bonus:.0f}점",
                                  (w // 2 - half - int(w * 0.02), int(h * 0.53)),
                                  max(22, h // 26), (255, 190, 110),
                                  anchor="rm", stroke=3))
        if state.result_remaining is not None:
            n = int(np.ceil(state.result_remaining))
            nxt = (f"{n}초 뒤 다음 자세 — {state.next_pose_name}"
                   if state.next_pose_name else f"{n}초 뒤 결과 화면")
            fs2 = max(20, h // 26)
            texts.append(TextItem(ellipsize(nxt, fs2, int(w * 0.66)),
                                  (w // 2, int(h * 0.69)), fs2,
                                  (220, 235, 255), anchor="mm"))

    elif state.state == State.DONE:
        translucent_rect(frame, 0, 0, w, h, alpha=0.68)
        texts.append(TextItem("유연성 리포트", (w // 2, int(h * 0.10)),
                              max(34, h // 14), (255, 255, 255), anchor="mm"))
        texts.append(TextItem(f"평균 {(state.final_summary or 0):.0f}점",
                              (w // 2, int(h * 0.19)), max(26, h // 20),
                              (120, 255, 140), anchor="mm"))
        report = state.report or [{"name": n, "score": s, "grade": "",
                                   "metrics": [], "asym_warn": False,
                                   "max_asymmetry": None} for n, s in state.results]
        panel(frame, int(w * 0.14), int(h * 0.24), int(w * 0.86), int(h * 0.96),
              radius=22, color=(12, 14, 24), alpha=0.55,
              border=(200, 150, 120), border_thickness=1)
        fs = max(17, h // 34)
        y = int(h * 0.30)
        row_h = int(h * 0.105)
        max_y = int(h * 0.90)
        for i, r in enumerate(report):
            if y > max_y:  # 자세가 많으면 넘치지 않게 요약
                texts.append(TextItem(f"… 외 {len(report) - i}개",
                                      (int(w * 0.22), y), max(14, fs - 3),
                                      (150, 160, 180), anchor="lm"))
                break
            texts.append(TextItem(ellipsize(r["name"], fs, int(w * 0.36)),
                                  (int(w * 0.22), y), fs,
                                  (235, 235, 235), anchor="lm"))
            texts.append(TextItem(f"{r['score']:.0f}점  {r.get('grade','')}",
                                  (int(w * 0.62), y), fs, (200, 230, 255), anchor="lm"))
            # 관절 각도(ROM) — 유효 지표 요약
            angs = [f"{e['measured']:.0f}°" for e in r.get("metrics", [])
                    if e.get("valid")]
            if angs:
                texts.append(TextItem("· " + " ".join(angs[:3]),
                                      (int(w * 0.22), y + int(fs * 1.1)),
                                      max(13, fs - 5), (150, 160, 180), anchor="lm"))
            if r.get("asym_warn"):
                texts.append(TextItem(f"! 좌우차 {r['max_asymmetry']:.0f}°",
                                      (int(w * 0.78), y), max(14, fs - 3),
                                      (255, 180, 120), anchor="lm"))
            y += row_h

    return draw_texts(frame, texts)


# BGR 색
P1_BGR = (166, 230, 46)   # 초록
P2_BGR = (255, 168, 74)   # 파랑
P1_RGB = (46, 230, 166)
P2_RGB = (74, 168, 255)


def compose_versus(frame: np.ndarray, p1pose: PersonPose | None,
                   p2pose: PersonPose | None, state: VersusState,
                   pass_accuracy: float = 85.0) -> np.ndarray:
    import cv2 as _cv2
    h, w = frame.shape[:2]
    texts: list[TextItem] = []

    # 중앙 분할선 — 점선으로 부드럽게
    for y0 in range(0, h, 26):
        _cv2.line(frame, (w // 2, y0), (w // 2, min(h, y0 + 13)),
                  (170, 180, 200), 1, _cv2.LINE_AA)
    if p1pose is not None:
        draw_skeleton(frame, p1pose, color=P1_BGR)
    if p2pose is not None:
        draw_skeleton(frame, p2pose, color=P2_BGR)

    if state.target_pose is not None:
        fs_t = max(20, h // 24)
        title = f"자세 {state.pose_index + 1}/{state.pose_total} · {state.target_pose.display_name}"
        texts.append(TextItem(ellipsize(title, fs_t, int(w * 0.72)),
                              (w // 2, int(h * 0.06)), fs_t, (255, 255, 255), anchor="mm"))
        if state.round_remaining is not None:
            texts.append(TextItem(f"{state.round_remaining:.0f}s", (w // 2, int(h * 0.12)),
                                  max(16, h // 34), (255, 210, 127), anchor="mm"))

    def panel(x0, label, rgb, p):
        texts.append(TextItem(f"{label}  {p.total:.0f}점", (int(x0), int(h * 0.155)),
                              max(18, h // 26), rgb, anchor="lm"))
        if state.state == VState.PLAYING:
            gx, gw = int(x0), int(w * 0.4)
            acc = p.accuracy
            gauge_bar(frame, gx, int(h * 0.25), gw, max(16, h // 30),
                      0 if acc is None else acc / 100.0,
                      fg=(0, 210, 0) if (acc is not None and acc >= pass_accuracy) else (60, 200, 200))
            texts.append(TextItem("정확도 --" if acc is None else f"정확도 {acc:.0f}%",
                                  (gx, int(h * 0.235)), max(14, h // 36), (255, 255, 255), anchor="lb"))
            gauge_bar(frame, gx, int(h * 0.32), gw, max(12, h // 40), p.hold_progress, fg=(230, 180, 40))
            if p.round_done:
                texts.append(TextItem("완료!", (gx + gw, int(h * 0.235)), max(16, h // 30),
                                      rgb, anchor="rb"))

    panel(w * 0.03, "P1", P1_RGB, state.p1)
    panel(w * 0.55, "P2", P2_RGB, state.p2)

    if state.state == VState.IDLE:
        translucent_rect(frame, 0, int(h * 0.42), w, int(h * 0.58))
        texts.append(TextItem(state.message, (w // 2, h // 2), max(26, h // 18),
                              (255, 255, 255), anchor="mm"))
    elif state.state == VState.COUNTDOWN:
        texts.append(TextItem(str(int(np.ceil(state.countdown_remaining or 0))),
                              (w // 2, h // 2), max(90, h // 4), (255, 255, 255),
                              anchor="mm", stroke=6))
    elif state.state == VState.DONE:
        translucent_rect(frame, 0, 0, w, h, alpha=0.75)
        wc = P1_RGB if state.winner == 1 else P2_RGB if state.winner == 2 else (255, 255, 255)
        texts.append(TextItem(state.message, (w // 2, int(h * 0.4)), max(44, h // 10),
                              wc, anchor="mm", stroke=4))
        texts.append(TextItem(f"P1  {state.p1.total:.0f}점", (w // 2, int(h * 0.56)),
                              max(26, h // 20), P1_RGB, anchor="mm"))
        texts.append(TextItem(f"P2  {state.p2.total:.0f}점", (w // 2, int(h * 0.66)),
                              max(26, h // 20), P2_RGB, anchor="mm"))

    return draw_texts(frame, texts)
