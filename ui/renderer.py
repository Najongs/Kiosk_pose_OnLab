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
    gauge_bar,
    panel,
    translucent_rect,
)
from core.pose_estimator import SKELETON_EDGES, PersonPose
from core.refs import REF_VIS
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


def _acc_colors(accuracy: float, pass_accuracy: float):
    """(cv2 BGR bar 색, PIL RGB 텍스트 색) 반환."""
    if accuracy >= pass_accuracy:
        return (0, 210, 0), (120, 255, 120)
    if accuracy >= pass_accuracy * 0.6:
        return (0, 200, 220), (255, 230, 120)
    return (60, 80, 235), (255, 140, 140)


def draw_guide(frame: np.ndarray, pose_name: str,
               ref_norm: list[list[float]] | None,
               anim_t: float | None = None) -> None:
    """목표 자세 예시를 화면 왼쪽 박스에 그린다.
    우선순위: 예시 이미지(config/examples/) > 참조 스켈레톤(관리자 캡처) > 빈 박스.
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

    imgs = example_images(pose_name)
    if imgs:
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
    elif ref_norm:
        px = lambda nx: int(ix + nx * iw)  # noqa: E731
        py = lambda ny: int(iy + ny * ih)  # noqa: E731
        for a, b in SKELETON_EDGES:
            if ref_norm[a][2] >= REF_VIS and ref_norm[b][2] >= REF_VIS:
                cv2.line(frame, (px(ref_norm[a][0]), py(ref_norm[a][1])),
                         (px(ref_norm[b][0]), py(ref_norm[b][1])), (127, 231, 160), 2, cv2.LINE_AA)


def _progress_dots(frame: np.ndarray, index: int, total: int, w: int, h: int) -> None:
    """상단바 우측: 자세 진행 도트 (완료=액센트, 현재=밝게, 남음=어둡게)."""
    if total < 2 or total > 20:
        return
    gap = 20
    cy = int(h * 0.055)
    x0 = w - 28 - (total - 1) * gap
    for i in range(total):
        cx = x0 + i * gap
        if i < index:
            cv2.circle(frame, (cx, cy), 5, (160, 231, 127), -1, cv2.LINE_AA)
        elif i == index:
            cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 8, (160, 231, 127), 1, cv2.LINE_AA)
        else:
            cv2.circle(frame, (cx, cy), 4, (96, 102, 124), -1, cv2.LINE_AA)


def compose(frame: np.ndarray, primary: PersonPose | None, state: SessionState,
            pass_accuracy: float = 85.0,
            ref_norm: list[list[float]] | None = None,
            anim_t: float | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []

    if primary is not None:
        draw_skeleton(frame, primary)

    if state.target_pose is not None and state.state in (State.COUNTDOWN, State.SCORING):
        draw_guide(frame, state.target_pose.name, ref_norm, anim_t)
        # 박스 상단 라벨 (좌측). 예시 이미지도 참조도 없으면 안내 문구
        texts.append(TextItem("따라해 보세요", (int(w * 0.02 + w * 0.09), int(h * 0.335)),
                              max(15, h // 42), (200, 220, 255), anchor="mm"))
        if not example_images(state.target_pose.name) and not ref_norm:
            texts.append(TextItem("예시 준비 중", (int(w * 0.02 + w * 0.09), int(h * 0.62)),
                                  max(13, h // 50), (150, 160, 180), anchor="mm"))

    # 상단 진행 바(자세 n/N + 자세명 + 진행 도트)
    if state.target_pose is not None:
        translucent_rect(frame, 0, 0, w, int(h * 0.11), color=(14, 16, 26), alpha=0.62)
        cv2.line(frame, (0, int(h * 0.11)), (w, int(h * 0.11)), (72, 120, 96), 1,
                 cv2.LINE_AA)
        texts.append(TextItem(f"자세 {state.pose_index + 1}/{state.pose_total}",
                              (24, int(h * 0.055)), max(20, h // 28),
                              (200, 220, 255), anchor="lm"))
        texts.append(TextItem(state.target_pose.display_name,
                              (int(w * 0.28), int(h * 0.055)), max(26, h // 20),
                              (255, 255, 255), anchor="lm"))
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
        frac = float(state.countdown_remaining or 0) % 1.0
        cv2.circle(frame, (w // 2, h // 2), r, (70, 76, 96), 6, cv2.LINE_AA)
        cv2.ellipse(frame, (w // 2, h // 2), (r, r), -90, 0, int(360 * frac),
                    (160, 231, 127), 6, cv2.LINE_AA)
        texts.append(TextItem(str(n), (w // 2, h // 2), max(90, h // 4),
                              (255, 255, 255), anchor="mm", stroke=6))
        texts.append(TextItem(state.message, (w // 2, int(h * 0.80)),
                              max(24, h // 22), (220, 235, 255), anchor="mm"))

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
        texts.append(TextItem(state.message, (w // 2, int(h * 0.80)),
                              max(22, h // 24), (255, 255, 255), anchor="mm"))

    elif state.state == State.RESULT:
        panel(frame, int(w * 0.14), int(h * 0.30), int(w * 0.86), int(h * 0.74),
              radius=24, color=(12, 14, 24), alpha=0.68,
              border=(127, 231, 160), border_thickness=2)
        score = state.last_score or 0.0
        texts.append(TextItem("완료!", (w // 2, int(h * 0.40)), max(34, h // 14),
                              (120, 255, 140), anchor="mm"))
        texts.append(TextItem(f"{score:.0f}점", (w // 2, int(h * 0.55)),
                              max(70, h // 6), (255, 255, 255), anchor="mm", stroke=5))
        if state.result_remaining is not None:
            n = int(np.ceil(state.result_remaining))
            nxt = (f"{n}초 뒤 다음 자세 — {state.next_pose_name}"
                   if state.next_pose_name else f"{n}초 뒤 결과 화면")
            texts.append(TextItem(nxt, (w // 2, int(h * 0.69)), max(20, h // 26),
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
            texts.append(TextItem(r["name"], (int(w * 0.22), y), fs,
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
        texts.append(TextItem(
            f"자세 {state.pose_index + 1}/{state.pose_total} · {state.target_pose.display_name}",
            (w // 2, int(h * 0.06)), max(20, h // 24), (255, 255, 255), anchor="mm"))
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
