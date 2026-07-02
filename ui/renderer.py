"""UI 화면 합성 (Qt 비의존).

세션 상태(SessionState)와 현재 포즈를 받아 키오스크 화면 한 장(BGR numpy)을
합성한다. Qt 창은 이 결과를 그대로 표시만 하면 되고, 헤드리스에서는 이 함수의
출력을 PNG 로 저장해 그대로 검증할 수 있다.
"""

from __future__ import annotations

import numpy as np

import cv2

from core.drawing import (
    TextItem,
    draw_skeleton,
    draw_texts,
    gauge_bar,
    translucent_rect,
)
from core.pose_estimator import SKELETON_EDGES, PersonPose
from core.refs import REF_VIS
from core.session import SessionState, State
from core.versus import VersusState, VState


def _acc_colors(accuracy: float, pass_accuracy: float):
    """(cv2 BGR bar 색, PIL RGB 텍스트 색) 반환."""
    if accuracy >= pass_accuracy:
        return (0, 210, 0), (120, 255, 120)
    if accuracy >= pass_accuracy * 0.6:
        return (0, 200, 220), (255, 230, 120)
    return (60, 80, 235), (255, 140, 140)


def draw_guide_thumbnail(frame: np.ndarray, ref_norm: list[list[float]] | None) -> None:
    """목표 자세 참조 스켈레톤을 우상단 썸네일 박스에 그린다(참조 있을 때만)."""
    if not ref_norm:
        return
    h, w = frame.shape[:2]
    bw = int(w * 0.2)
    bh = int(bw * 1.25)
    bx = w - bw - int(w * 0.02)
    by = int(h * 0.14)
    translucent_rect(frame, bx, by, bx + bw, by + bh, color=(30, 24, 12), alpha=0.65)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 190, 90), 2)
    pad = int(bw * 0.14)
    ix, iy = bx + pad, by + int(bh * 0.14)
    iw, ih = bw - pad * 2, bh - int(bh * 0.14) - pad
    px = lambda nx: int(ix + nx * iw)  # noqa: E731
    py = lambda ny: int(iy + ny * ih)  # noqa: E731
    for a, b in SKELETON_EDGES:
        if ref_norm[a][2] >= REF_VIS and ref_norm[b][2] >= REF_VIS:
            cv2.line(frame, (px(ref_norm[a][0]), py(ref_norm[a][1])),
                     (px(ref_norm[b][0]), py(ref_norm[b][1])), (127, 231, 160), 2, cv2.LINE_AA)


def compose(frame: np.ndarray, primary: PersonPose | None, state: SessionState,
            pass_accuracy: float = 85.0,
            ref_norm: list[list[float]] | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []

    if primary is not None:
        draw_skeleton(frame, primary)

    if state.target_pose is not None and state.state in (State.COUNTDOWN, State.SCORING):
        draw_guide_thumbnail(frame, ref_norm)
        texts.append(TextItem("목표 자세", (int(w - w * 0.12), int(h * 0.155)),
                              max(16, h // 40), (200, 220, 255), anchor="mm"))

    # 상단 진행 바(자세 n/N + 자세명)
    if state.target_pose is not None:
        translucent_rect(frame, 0, 0, w, int(h * 0.11))
        texts.append(TextItem(f"자세 {state.pose_index + 1}/{state.pose_total}",
                              (24, int(h * 0.055)), max(20, h // 28),
                              (200, 220, 255), anchor="lm"))
        texts.append(TextItem(state.target_pose.display_name,
                              (int(w * 0.28), int(h * 0.055)), max(26, h // 20),
                              (255, 255, 255), anchor="lm"))

    if state.state == State.IDLE:
        translucent_rect(frame, 0, int(h * 0.42), w, int(h * 0.58))
        texts.append(TextItem(state.message, (w // 2, h // 2), max(30, h // 16),
                              (255, 255, 255), anchor="mm"))

    elif state.state == State.COUNTDOWN:
        n = int(np.ceil(state.countdown_remaining or 0))
        texts.append(TextItem(str(n), (w // 2, h // 2), max(90, h // 4),
                              (255, 255, 255), anchor="mm", stroke=6))
        texts.append(TextItem(state.message, (w // 2, int(h * 0.80)),
                              max(24, h // 22), (220, 235, 255), anchor="mm"))

    elif state.state == State.SCORING:
        acc = state.accuracy
        # 정확도 게이지(좌측)
        gx, gy, gw, gh = 24, int(h * 0.16), int(w * 0.28), max(22, h // 26)
        if acc is not None:
            bar_c, txt_c = _acc_colors(acc, pass_accuracy)
            gauge_bar(frame, gx, gy, gw, gh, acc / 100.0, fg=bar_c)
            texts.append(TextItem(f"정확도 {acc:.0f}%", (gx, gy - 8),
                                  max(20, h // 30), txt_c, anchor="lb"))
        else:
            gauge_bar(frame, gx, gy, gw, gh, 0.0)
            texts.append(TextItem("정확도 --", (gx, gy - 8), max(20, h // 30),
                                  (220, 220, 220), anchor="lb"))
        # 유지 진행 바(하단)
        hx, hy, hw, hh = int(w * 0.2), int(h * 0.88), int(w * 0.6), max(18, h // 34)
        gauge_bar(frame, hx, hy, hw, hh, state.hold_progress, fg=(230, 180, 40))
        texts.append(TextItem("유지", (hx - 12, hy + hh // 2), max(18, h // 34),
                              (255, 235, 180), anchor="rm"))
        texts.append(TextItem(state.message, (w // 2, int(h * 0.80)),
                              max(22, h // 24), (255, 255, 255), anchor="mm"))

    elif state.state == State.RESULT:
        translucent_rect(frame, 0, int(h * 0.30), w, int(h * 0.70), alpha=0.6)
        score = state.last_score or 0.0
        texts.append(TextItem("완료!", (w // 2, int(h * 0.42)), max(34, h // 14),
                              (120, 255, 140), anchor="mm"))
        texts.append(TextItem(f"{score:.0f}점", (w // 2, int(h * 0.58)),
                              max(70, h // 6), (255, 255, 255), anchor="mm", stroke=5))

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
        fs = max(17, h // 34)
        y = int(h * 0.28)
        for r in report:
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
            y += int(h * 0.11)

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

    _cv2.line(frame, (w // 2, 0), (w // 2, h), (200, 200, 200), 1)
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
